from datetime import datetime
from types import SimpleNamespace

import pytest
import pytest_asyncio
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.methods import EditMessageText, SendMessage
from aiogram.types import CallbackQuery, Update, Message, Chat, User

from controlpribor_bot.bot import setup_dispatcher
from controlpribor_bot.config import Config
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.handlers import catalog
from controlpribor_bot.handlers.admin import (
    AdminAddProductStates,
    AdminCategoryStates,
    extract_image,
)
from controlpribor_bot.keyboards.admin_kb import (
    PICKER_PER_PAGE,
    get_admin_main_kb,
    get_picker_kb,
    get_product_admin_actions_kb,
    get_category_admin_card_kb,
)

ADMIN_ID = 111


@pytest_asyncio.fixture
async def db(tmp_path):
    manager = DatabaseManager(f"sqlite+aiosqlite:///{tmp_path / 'edit.db'}")
    await manager.init_db()
    yield manager
    await manager.close()


# --- Ma'lumotlar bazasi ---
@pytest.mark.asyncio
async def test_brand_delete_sets_product_brand_null(db: DatabaseManager):
    brand = await db.add_brand("X Brand", "x-brand")
    cat = await db.add_category("X Cat", brand_id=brand.id)
    prod = await db.add_product("X Tool", brand_id=brand.id, category_id=cat.id)

    await db.delete_brand(brand.id)

    assert (await db.get_product_by_id(prod.id)).brand_id is None
    assert (await db.get_category_by_id(cat.id)).brand_id is None


@pytest.mark.asyncio
async def test_category_delete_sets_product_category_null(db: DatabaseManager):
    cat = await db.add_category("Y Cat")
    prod = await db.add_product("Y Tool", category_id=cat.id)

    await db.delete_category(cat.id)

    assert (await db.get_product_by_id(prod.id)).category_id is None


@pytest.mark.asyncio
async def test_product_delete_cascades_cart(db: DatabaseManager):
    user, _ = await db.get_or_create_user(1, "Test", "+998")
    prod = await db.add_product("Z Tool")
    await db.add_to_cart(user.id, prod.id)

    await db.delete_product(prod.id)

    assert await db.get_cart_items(user.id) == []


@pytest.mark.asyncio
async def test_add_brand_same_slug_returns_existing(db: DatabaseManager):
    chint = await db.add_brand("Chint", "chint")
    again = await db.add_brand("CHINT", "chint")
    assert again.id == chint.id


@pytest.mark.asyncio
async def test_update_brand(db: DatabaseManager):
    a = await db.add_brand("Alpha", "alpha")
    await db.add_brand("Beta", "beta")

    renamed = await db.update_brand(a.id, "Alpha Pro", "alpha-pro")
    assert renamed.name == "Alpha Pro"
    assert renamed.slug == "alpha-pro"

    with pytest.raises(ValueError):
        await db.update_brand(a.id, "beta", "beta")
    assert await db.update_brand(9999, "Nope", "nope") is None


@pytest.mark.asyncio
async def test_update_category_fields(db: DatabaseManager):
    brand = await db.add_brand("Fluke", "fluke")
    cat = await db.add_category("Kleshlar")
    await db.add_category("Multimetrlar")

    updated = await db.update_category_fields(cat.id, name="Tok kleshlari", brand_id=brand.id)
    assert updated.name == "Tok kleshlari"
    assert updated.brand.name == "Fluke"  # sessiyadan tashqarida yuklangan

    cleared = await db.update_category_fields(cat.id, brand_id=None)
    assert cleared.brand_id is None

    with pytest.raises(ValueError):
        await db.update_category_fields(cat.id, name="MULTIMETRLAR")


@pytest.mark.asyncio
async def test_update_product_fields_returns_loaded_relations(db: DatabaseManager):
    brand = await db.add_brand("Testo", "testo")
    cat = await db.add_category("Termometrlar")
    prod = await db.add_product("Testo 830")

    updated = await db.update_product_fields(prod.id, brand_id=brand.id, category_id=cat.id)
    assert updated.brand.name == "Testo"
    assert updated.category.name == "Termometrlar"


@pytest.mark.asyncio
async def test_get_all_categories_without_limit(db: DatabaseManager):
    base = len(await db.get_all_categories())
    for i in range(110):
        await db.add_category(f"Cat {i}")
    cats = await db.get_all_categories()
    assert len(cats) == base + 110
    assert all(c.brand is None for c in cats)  # brand oldindan yuklangan, xato bermaydi


@pytest.mark.asyncio
async def test_get_product_by_name_case_insensitive(db: DatabaseManager):
    prod = await db.add_product("Fluke 107")
    assert (await db.get_product_by_name("fluke 107")).id == prod.id
    assert await db.get_product_by_name("Fluke 108") is None


# --- Klaviaturalar ---
def _buttons(kb):
    return [btn for row in kb.inline_keyboard for btn in row]


def test_picker_kb_paginates_and_has_none_option():
    items = [SimpleNamespace(id=i, name=f"Brand {i}") for i in range(1, 26)]

    first = _buttons(get_picker_kb(items, "pb", "admin_prod_b_", "🚫 Brendsiz", page=1))
    picks = [b for b in first if b.callback_data.startswith("admin_prod_b_") and b.callback_data != "admin_prod_b_0"]
    assert len(picks) == PICKER_PER_PAGE
    assert any(b.callback_data == "admin_pick_pb_2" for b in first)
    assert any(b.callback_data == "admin_prod_b_0" for b in first)

    last = _buttons(get_picker_kb(items, "pb", "admin_prod_b_", "🚫 Brendsiz", page=3))
    assert any(b.callback_data == "admin_prod_b_25" for b in last)
    assert not any(b.callback_data == "admin_pick_pb_4" for b in last)


def test_admin_card_keyboards():
    prod_cbs = [b.callback_data for b in _buttons(get_product_admin_actions_kb(7, category_id=3))]
    assert "admin_prod_edit_cat_7" in prod_cbs
    assert "admin_cat_prods_3_1" in prod_cbs  # tovardan o'z bo'limiga qaytish
    assert not any("brand" in cb for cb in prod_cbs)  # brend endi tahrirlanmaydi

    cat_cbs = [b.callback_data for b in _buttons(get_category_admin_card_kb(5))]
    assert {"admin_cat_prods_5_1", "admin_cat_rename_5", "admin_cat_del_5"} <= set(cat_cbs)
    assert not any("brand" in cb for cb in cat_cbs)

    main_cbs = [b.callback_data for b in _buttons(get_admin_main_kb())]
    assert "admin_brands" not in main_cbs and "admin_categories" in main_cbs


# --- Yordamchi funksiyalar ---
def test_extract_image_uses_file_id_not_token():
    photo_msg = SimpleNamespace(photo=[SimpleNamespace(file_id="small"), SimpleNamespace(file_id="BIG_ID")], text=None)
    assert extract_image(photo_msg) == "BIG_ID"

    url_msg = SimpleNamespace(photo=None, text="https://example.com/a.jpg")
    assert extract_image(url_msg) == "https://example.com/a.jpg"

    bad_msg = SimpleNamespace(photo=None, text="rasm emas")
    assert extract_image(bad_msg) is None


def test_invalidate_photo_cache():
    catalog._PHOTO_CACHE[42] = "old_file_id"
    catalog.invalidate_photo_cache(42)
    assert 42 not in catalog._PHOTO_CACHE
    catalog.invalidate_photo_cache(42)  # yo'q kalit xato bermaydi


# --- Handlerlar (soxta Telegram sessiyasi orqali) ---
class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.requests = []

    async def make_request(self, bot, method, timeout=None):
        self.requests.append(method)
        return True

    async def stream_content(self, *args, **kwargs):
        yield b""

    async def close(self):
        pass


def _text_update(text: str, update_id: int = 1) -> Update:
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.now(),
            chat=Chat(id=ADMIN_ID, type="private"),
            from_user=User(id=ADMIN_ID, is_bot=False, first_name="Admin"),
            text=text,
        ),
    )


@pytest_asyncio.fixture
async def bot_env(db):
    config = Config(BOT_TOKEN="123456:TEST", ORDER_GROUP_ID=0, ADMIN_IDS=[ADMIN_ID])
    session = FakeSession()
    bot = Bot(token=config.BOT_TOKEN, session=session)
    dp = setup_dispatcher(db=db, config=config)
    state = dp.fsm.get_context(bot=bot, chat_id=ADMIN_ID, user_id=ADMIN_ID)
    return SimpleNamespace(bot=bot, dp=dp, db=db, session=session, state=state)


def _sent_texts(session):
    return [m.text for m in session.requests if isinstance(m, SendMessage)]


def _callback_update(data: str, update_id: int) -> Update:
    admin = User(id=ADMIN_ID, is_bot=False, first_name="Admin")
    return Update(
        update_id=update_id,
        callback_query=CallbackQuery(
            id=str(update_id), from_user=admin, chat_instance="ci", data=data,
            message=Message(message_id=500, date=datetime.now(), chat=Chat(id=ADMIN_ID, type="private"),
                            from_user=admin, text="menu"),
        ),
    )


def _last_markup_callbacks(session):
    markups = [m.reply_markup for m in session.requests
               if isinstance(m, (SendMessage, EditMessageText)) and m.reply_markup]
    return [b.callback_data for row in markups[-1].inline_keyboard for b in row]


@pytest.mark.asyncio
async def test_menu_button_in_admin_fsm_is_not_saved_as_data(bot_env):
    await bot_env.state.set_state(AdminCategoryStates.waiting_for_name)

    await bot_env.dp.feed_update(bot_env.bot, _text_update("📦 Tovarlar"))

    assert await bot_env.state.get_state() is None
    assert await bot_env.db.find_category("📦 Tovarlar") is None
    # Tugma o'z ishini bajardi: mijozning "Tovarlar" menyusi ko'rsatildi
    assert any("Tovarlar" in (t or "") for t in _sent_texts(bot_env.session))


@pytest.mark.asyncio
async def test_add_product_without_brand_step(bot_env):
    db = bot_env.db
    akfix = await db.find_category("AKFIX")

    await bot_env.dp.feed_update(bot_env.bot, _callback_update("admin_prod_add", 1))
    await bot_env.dp.feed_update(bot_env.bot, _text_update("AKFIX 705 <yangi>", 2))

    # Nomdan keyin darhol bo'lim tanlanadi: brend yo'q, "Kategoriyasiz" varianti ham yo'q
    assert await bot_env.state.get_state() == AdminAddProductStates.waiting_for_category.state
    picker = _last_markup_callbacks(bot_env.session)
    assert picker[0] == f"admin_prod_c_{akfix.id}"  # mijozdagi tartibda — AKFIX birinchi
    assert "admin_prod_c_0" not in picker and not any("brand" in cb or "_b_" in cb for cb in picker)

    await bot_env.dp.feed_update(bot_env.bot, _callback_update(f"admin_prod_c_{akfix.id}", 3))
    await bot_env.dp.feed_update(bot_env.bot, _text_update("4.5$", 4))
    await bot_env.dp.feed_update(bot_env.bot, _callback_update("admin_fsm_skip", 5))  # rasm
    await bot_env.dp.feed_update(bot_env.bot, _callback_update("admin_fsm_skip", 6))  # tavsif

    assert await bot_env.state.get_state() is None
    product = await db.get_product_by_name("AKFIX 705 <yangi>")
    product = await db.get_product_by_id(product.id)
    assert product.category.name == "AKFIX"
    assert product.brand is None and product.price == "4.5$"


@pytest.mark.asyncio
async def test_admin_category_list_and_products(bot_env):
    db = bot_env.db
    tess = await db.find_category("TESS")
    lamp = await db.add_product("TESS LED 15W", category_id=tess.id)

    await bot_env.dp.feed_update(bot_env.bot, _callback_update("admin_cat_list_1", 1))
    edits = [m for m in bot_env.session.requests if isinstance(m, EditMessageText)]
    first_page = [b.text for row in edits[-1].reply_markup.inline_keyboard for b in row]
    assert first_page[0] == "🧴 AKFIX (0)" and "💡 TESS (1)" in first_page  # mijozdagi tartib + soni

    await bot_env.dp.feed_update(bot_env.bot, _callback_update(f"admin_cat_prods_{tess.id}_1", 2))
    assert f"admin_prod_view_{lamp.id}" in _last_markup_callbacks(bot_env.session)


@pytest.mark.asyncio
async def test_rename_category_conflict_keeps_state(bot_env):
    cat = await bot_env.db.add_category("Rele")
    await bot_env.db.add_category("Kabel")
    await bot_env.state.set_state(AdminCategoryStates.waiting_for_new_name)
    await bot_env.state.update_data(edit_cat_id=cat.id)

    await bot_env.dp.feed_update(bot_env.bot, _text_update("kabel"))

    assert (await bot_env.db.get_category_by_id(cat.id)).name == "Rele"
    assert await bot_env.state.get_state() == AdminCategoryStates.waiting_for_new_name.state
