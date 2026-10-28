from datetime import datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.methods import AnswerCallbackQuery, SendMessage
from aiogram.types import CallbackQuery, Chat, Message, Update, User

from controlpribor_bot.bot import setup_dispatcher
from controlpribor_bot.config import Config
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.handlers.cart import CheckoutStates, deliver_order
from controlpribor_bot.handlers.start import NO_PHONE, has_phone, normalize_phone, save_registration
from test_admin_edit import FakeSession

USER_ID = 222
ADMIN_ID = 111


@pytest_asyncio.fixture
async def db(tmp_path):
    manager = DatabaseManager(f"sqlite+aiosqlite:///{tmp_path / 'orders.db'}")
    await manager.init_db()
    yield manager
    await manager.close()


# --- Qidiruv ---
@pytest.mark.asyncio
async def test_search_is_case_insensitive_for_cyrillic(db: DatabaseManager):
    await db.add_product("XITE метр Рулетка", price="0.87$")
    for query in ["рулетка", "РУЛЕТКА", "Рулетка", "xite"]:
        products, total = await db.search_products(query)
        assert total == 1, query
        assert products[0].name == "XITE метр Рулетка"


@pytest.mark.asyncio
async def test_search_finds_variant_codes_in_description_name_matches_first(db: DatabaseManager):
    await db.add_product("CHINT — Контактор 3P NC1", description="Контактор 3P NC1-(0910) 220V — 6,10")
    await db.add_product("NC1-0910 kontaktor")

    products, total = await db.search_products("0910")
    assert total == 2
    assert products[0].name == "NC1-0910 kontaktor"  # nomida topilgani birinchi

    _, total = await db.search_products("100%")  # maxsus belgilar shablon emas
    assert total == 0


# --- Telefon ---
def test_normalize_phone():
    assert normalize_phone("+998 90 123-45-67") == "+998901234567"
    assert normalize_phone("998901234567") == "+998901234567"
    assert normalize_phone("12345") is None
    assert normalize_phone(None) is None


@pytest.mark.asyncio
async def test_registration_fills_phone_of_user_created_from_cart(db: DatabaseManager):
    await db.get_or_create_user(USER_ID, "Mijoz", NO_PHONE)
    assert not has_phone(await db.get_user_by_telegram_id(USER_ID))

    await save_registration(db, USER_ID, "Ali Valiyev", "+998901234567")

    user = await db.get_user_by_telegram_id(USER_ID)
    assert user.phone_number == "+998901234567"
    assert has_phone(user)


# --- Buyurtmani yetkazish ---
class RecordingBot:
    def __init__(self, failing_chats=()):
        self.failing_chats = set(failing_chats)
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode=None):
        if chat_id in self.failing_chats:
            raise RuntimeError("chat not found")
        self.sent.append(chat_id)


def make_config(group_id=0, admins=(ADMIN_ID,)):
    return Config(BOT_TOKEN="123456:TEST", ORDER_GROUP_ID=group_id, ADMIN_IDS=list(admins))


@pytest.mark.asyncio
async def test_order_goes_to_group_when_it_works():
    bot = RecordingBot()
    assert await deliver_order(bot, make_config(group_id=-100), 1, "text")
    assert bot.sent == [-100]


@pytest.mark.asyncio
async def test_order_falls_back_to_admins_when_group_fails():
    bot = RecordingBot(failing_chats={-100})
    assert await deliver_order(bot, make_config(group_id=-100, admins=(1, 2)), 1, "text")
    assert bot.sent == [1, 2]


@pytest.mark.asyncio
async def test_order_falls_back_to_admins_when_group_not_configured():
    bot = RecordingBot()
    assert await deliver_order(bot, make_config(group_id=0), 1, "text")
    assert bot.sent == [ADMIN_ID]


@pytest.mark.asyncio
async def test_order_not_delivered_is_reported():
    bot = RecordingBot(failing_chats={ADMIN_ID})
    assert not await deliver_order(bot, make_config(group_id=0), 1, "text")


# --- Handlerlar orqali to'liq oqim ---
@pytest_asyncio.fixture
async def env(db):
    config = make_config(group_id=-100)
    session = FakeSession()
    bot = Bot(token=config.BOT_TOKEN, session=session)
    dp = setup_dispatcher(db=db, config=config)
    state = dp.fsm.get_context(bot=bot, chat_id=USER_ID, user_id=USER_ID)
    return SimpleNamespace(bot=bot, dp=dp, db=db, session=session, state=state)


def _user():
    return User(id=USER_ID, is_bot=False, first_name="Mijoz")


def _message(text=None, update_id=1, **kwargs):
    msg = Message(
        message_id=update_id, date=datetime.now(), chat=Chat(id=USER_ID, type="private"),
        from_user=_user(), text=text, **kwargs,
    )
    return msg


def _callback(data: str, update_id=1) -> Update:
    return Update(
        update_id=update_id,
        callback_query=CallbackQuery(
            id=str(update_id), from_user=_user(), chat_instance="ci", data=data,
            message=_message("menu", update_id=100 + update_id),
        ),
    )


@pytest.mark.asyncio
async def test_checkout_without_phone_asks_for_it_then_places_order(env):
    user, _ = await env.db.get_or_create_user(USER_ID, "Mijoz", NO_PHONE)
    prod = await env.db.add_product("SMASH степлер", price="4.5$")
    await env.db.add_to_cart(user.id, prod.id, 2)

    await env.dp.feed_update(env.bot, _callback("checkout_order"))
    assert await env.state.get_state() == CheckoutStates.waiting_for_phone.state
    assert await env.db.get_cart_items(user.id)  # buyurtma hali yaratilmagan

    # Telefon raqami qidiruvga ketmasligi kerak — buyurtma rasmiylashadi
    await env.dp.feed_update(env.bot, Update(update_id=2, message=_message("+998 90 123 45 67", update_id=2)))

    assert await env.state.get_state() is None
    assert (await env.db.get_user_by_telegram_id(USER_ID)).phone_number == "+998901234567"
    assert await env.db.get_cart_items(user.id) == []
    group_msgs = [m for m in env.session.requests if isinstance(m, SendMessage) and m.chat_id == -100]
    assert len(group_msgs) == 1
    assert "+998901234567" in group_msgs[0].text and "9$" in group_msgs[0].text


@pytest.mark.asyncio
async def test_empty_category_shows_single_alert(env):
    cat = await env.db.add_category("Bo'sh toifa")

    await env.dp.feed_update(env.bot, _callback(f"cat_{cat.id}"))

    answers = [m for m in env.session.requests if isinstance(m, AnswerCallbackQuery)]
    assert len(answers) == 1
    assert answers[0].show_alert and "topilmadi" in answers[0].text


# --- "📦 Tovarlar" menyusi ---
@pytest.mark.asyncio
async def test_shop_categories_order(db: DatabaseManager):
    from controlpribor_bot.database.db_manager import DEFAULT_CATEGORIES

    other = await db.add_category("Boshqa tovarlar")
    extra = await db.add_category("Admin kategoriyasi")
    await db.add_category("Bo'sh qo'shimcha")
    await db.add_product("A", category_id=other.id)
    await db.add_product("B", category_id=extra.id)

    names = [c.name for c in await db.get_shop_categories()]
    assert names == DEFAULT_CATEGORIES + ["Admin kategoriyasi", "Boshqa tovarlar"]


@pytest.mark.asyncio
async def test_products_button_shows_all_shop_categories(env):
    await env.dp.feed_update(env.bot, Update(update_id=1, message=_message("📦 Tovarlar")))

    sent = [m for m in env.session.requests if isinstance(m, SendMessage)]
    assert len(sent) == 1
    buttons = [b.text for row in sent[0].reply_markup.inline_keyboard for b in row]
    assert len(buttons) == 16 and buttons[0] == "🧴 AKFIX" and buttons[-1] == "💡 LEZARD"


@pytest.mark.asyncio
async def test_legacy_menu_button_refreshes_keyboard(env):
    await env.dp.feed_update(env.bot, Update(update_id=1, message=_message("🏷 Brendlar")))

    sent = [m for m in env.session.requests if isinstance(m, SendMessage)]
    assert len(sent) == 2  # yangi menyu + bo'limlar
    menu_buttons = [b.text for row in sent[0].reply_markup.keyboard for b in row]
    assert "📦 Tovarlar" in menu_buttons
    assert "Tovarlar" in sent[1].text
