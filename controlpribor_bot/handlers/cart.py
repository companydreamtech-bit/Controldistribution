import html
import logging
import re
from datetime import datetime
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from controlpribor_bot.config import Config
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.handlers.start import has_phone, normalize_phone
from controlpribor_bot.keyboards.default_kb import get_contact_kb, get_main_menu_kb
from controlpribor_bot.keyboards.inline_kb import get_cart_kb

cart_router = Router(name="cart_router")
logger = logging.getLogger(__name__)


def parse_price(price_str: str) -> tuple[Optional[float], str]:
    """Narxni (miqdor, valyuta) ga ajratish: "1 500 000 so'm" -> (1500000, "so'm"), "0.87$" -> (0.87, "$").

    Diapazon ("0.4$ – 1.1$", variantli tovar) va "Kelishilgan holda" -> (None, "").
    """
    price_str = price_str or ""
    if "$" in price_str:
        amounts = re.findall(r"\d{1,3}(?:[  ]\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?", price_str)
        if len(amounts) != 1:
            return None, ""
        return float(re.sub(r"[  ]", "", amounts[0]).replace(",", ".")), "$"
    if "–" in price_str:
        return None, ""
    digits = "".join(filter(str.isdigit, price_str))
    return (float(digits), "so'm") if digits else (None, "")


def format_amount(value: float, currency: str) -> str:
    if currency == "$":
        return f"{value:,.2f}".rstrip("0").rstrip(".").replace(",", " ") + "$"
    return f"{int(value):,}".replace(",", " ") + " so'm"


def format_cart_message(items: list) -> tuple[str, str]:
    """Savatcha matnini va umumiy summani formatlash (so'm va $ alohida jamlanadi)."""
    if not items:
        return "🛒 <b>Sizning savatchangiz bo'sh.</b>\n\nKatalogdan kerakli tovarlarni tanlang!", "0 so'm"

    lines = ["🛒 <b>SIZNING SAVATCHANGIZ:</b>\n"]
    totals = {"so'm": 0.0, "$": 0.0}
    has_custom_price = False

    for idx, itm in enumerate(items, start=1):
        name = html.escape(itm["product_name"])
        qty = itm["quantity"]
        price_str = itm["price"]

        item_price, currency = parse_price(price_str)
        if item_price is not None:
            item_total = item_price * qty
            totals[currency] += item_total
            lines.append(
                f"<b>{idx}. {name}</b>\n"
                f"   {qty} dona × {format_amount(item_price, currency)} = "
                f"<b>{format_amount(item_total, currency)}</b>\n"
            )
        else:
            has_custom_price = True
            lines.append(f"<b>{idx}. {name}</b>\n   {qty} dona × <i>{html.escape(price_str)}</i>\n")

    lines.append("────────────────────────")
    parts = [format_amount(total, cur) for cur, total in totals.items() if total > 0]
    if parts:
        total_formatted = " + ".join(parts)
        if has_custom_price:
            total_formatted += " (+ kelishilgan tovarlar)"
    else:
        total_formatted = "Kelishilgan holda"

    lines.append(f"💰 <b>Jami summa:</b> {total_formatted}")
    return "\n".join(lines), total_formatted


@cart_router.message(F.text == "🛒 Savatcha")
async def show_cart(message: Message, db: DatabaseManager):
    user = await db.get_user_by_telegram_id(message.from_user.id)
    if not user:
        await message.answer("Iltimos, avval /start buyrug'i orqali ro'yxatdan o'ting.")
        return

    items = await db.get_cart_items(user_id=user.id)
    text, _ = format_cart_message(items)
    await message.answer(text, reply_markup=get_cart_kb(items), parse_mode="HTML")


@cart_router.callback_query(F.data.startswith("cart_plus_") | F.data.startswith("cart_minus_"))
async def update_cart_item_qty(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer()
    parts = callback.data.split("_")
    action = parts[1]
    cart_id = int(parts[2])
    current_qty = int(parts[3])

    if action == "plus":
        new_qty = current_qty + 1
    else:
        new_qty = current_qty - 1

    await db.update_cart_quantity(cart_id, new_qty)

    user = await db.get_user_by_telegram_id(callback.from_user.id)
    items = await db.get_cart_items(user_id=user.id)
    text, _ = format_cart_message(items)
    await callback.message.edit_text(text, reply_markup=get_cart_kb(items), parse_mode="HTML")


@cart_router.callback_query(F.data.startswith("cart_del_"))
async def delete_cart_item(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer("Mahsulot savatchadan o'chirildi!", show_alert=False)
    cart_id = int(callback.data.split("_")[2])
    await db.remove_from_cart(cart_id)

    user = await db.get_user_by_telegram_id(callback.from_user.id)
    items = await db.get_cart_items(user_id=user.id)
    text, _ = format_cart_message(items)
    await callback.message.edit_text(text, reply_markup=get_cart_kb(items), parse_mode="HTML")


@cart_router.callback_query(F.data == "clear_cart")
async def clear_cart_handler(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer("Savatcha tozalandi!", show_alert=False)
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if user:
        await db.clear_cart(user_id=user.id)

    await callback.message.edit_text(
        "🛒 <b>Sizning savatchangiz bo'shatildi.</b>",
        parse_mode="HTML",
    )


class CheckoutStates(StatesGroup):
    waiting_for_phone = State()


def build_order_message(order_id: int, user, tg_user, items: list, total_price: str) -> str:
    """Xodimlarga yuboriladigan buyurtma matni."""
    order_lines = [
        f"{idx}. {html.escape(itm['product_name'])} — {itm['quantity']} dona (Narxi: {html.escape(itm['price'])})"
        for idx, itm in enumerate(items, start=1)
    ]
    username = f"@{tg_user.username}" if tg_user.username else f"ID: {tg_user.id}"
    items_block = "\n".join(order_lines)
    return (
        f"🔔 <b>YANGI BUYURTMA #{order_id}</b>\n"
        f"👤 <b>Mijoz:</b> {html.escape(user.full_name)}\n"
        f"📞 <b>Telefon:</b> {html.escape(user.phone_number)}\n"
        f"💬 <b>Telegram:</b> {username}\n"
        f"────────────────────────────────\n"
        f"📦 <b>Mahsulotlar:</b>\n"
        f"{items_block}\n"
        f"────────────────────────────────\n"
        f"💰 <b>Jami:</b> {html.escape(total_price)}\n"
        f"⏰ <b>Vaqti:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )


async def deliver_order(bot: Bot, config: Config, order_id: int, text: str) -> bool:
    """Buyurtmani xodimlar guruhiga, u ishlamasa — adminlarga shaxsiy xabar qilib yuborish."""
    if config.ORDER_GROUP_ID:
        try:
            await bot.send_message(chat_id=config.ORDER_GROUP_ID, text=text, parse_mode="HTML")
            return True
        except Exception:
            logger.exception("Buyurtma #%s guruhga (%s) yuborilmadi", order_id, config.ORDER_GROUP_ID)
    else:
        logger.warning("ORDER_GROUP_ID sozlanmagan, buyurtma #%s adminlarga yuboriladi", order_id)

    delivered = False
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="⚠️ <i>Buyurtmalar guruhiga yuborib bo'lmadi, sizga yuborilmoqda.</i>\n\n" + text,
                parse_mode="HTML",
            )
            delivered = True
        except Exception:
            logger.exception("Buyurtma #%s admin %s ga yuborilmadi", order_id, admin_id)
    if not delivered:
        logger.error("Buyurtma #%s hech kimga yetkazilmadi! Faqat bazada saqlangan.", order_id)
    return delivered


async def place_order(target: Message, tg_user, user, db: DatabaseManager, bot: Bot, config: Config) -> bool:
    """Savatchadan buyurtma yaratish, xodimlarga yuborish va mijozga javob berish."""
    items = await db.get_cart_items(user_id=user.id)
    if not items:
        await target.answer("🛒 Savatchangiz bo'sh.")
        return False

    _, total_price = format_cart_message(items)
    order = await db.create_order(user_id=user.id, total_price=total_price, items=items)
    await deliver_order(bot, config, order.id, build_order_message(order.id, user, tg_user, items, total_price))
    await db.clear_cart(user_id=user.id)

    await target.answer(
        f"✅ <b>Buyurtmangiz muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"🆔 <b>Buyurtma raqami:</b> #{order.id}\n"
        f"💰 <b>Summa:</b> {html.escape(total_price)}\n\n"
        f"Operatorimiz tez orada siz bilan bog'lanadi va yetkazib berish shartlarini kelishadi.\n"
        f"Xaridingiz uchun rahmat!",
        reply_markup=get_main_menu_kb(is_admin=config.is_admin(tg_user.id)),
        parse_mode="HTML",
    )
    return True


@cart_router.callback_query(F.data == "checkout_order")
async def checkout_order_handler(
    callback: CallbackQuery, state: FSMContext, db: DatabaseManager, bot: Bot, config: Config
):
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return

    if not await db.get_cart_items(user_id=user.id):
        await callback.answer("Savatchangiz bo'sh!", show_alert=True)
        return

    await callback.answer()
    # Telefonsiz buyurtma xodimlarga foydasiz — avval raqamni so'raymiz
    if not has_phone(user):
        await state.set_state(CheckoutStates.waiting_for_phone)
        await callback.message.answer(
            "📞 <b>Buyurtmani rasmiylashtirish uchun telefon raqamingizni yuboring.</b>\n\n"
            "Pastdagi <b>«📱 Telefon raqamni yuborish»</b> tugmasini bosing yoki raqamni yozing:\n"
            "<i>(Masalan: +998901234567)</i>",
            reply_markup=get_contact_kb(),
            parse_mode="HTML",
        )
        return

    try:
        await callback.message.delete()
    except Exception:
        pass
    await place_order(callback.message, callback.from_user, user, db, bot, config)


@cart_router.message(CheckoutStates.waiting_for_phone, F.contact | F.text)
async def checkout_phone_received(
    message: Message, state: FSMContext, db: DatabaseManager, bot: Bot, config: Config
):
    raw = message.contact.phone_number if message.contact else message.text
    phone = normalize_phone(raw)
    if not phone:
        await message.answer(
            "⚠️ <b>Iltimos, telefon raqamingizni to'g'ri formatda kiriting:</b>\n"
            "<i>(Masalan: +998901234567)</i> yoki pastdagi tugmani bosing:",
            reply_markup=get_contact_kb(),
            parse_mode="HTML",
        )
        return

    user = await db.update_user_phone(message.from_user.id, phone)
    await state.clear()
    if not user:
        await message.answer("Iltimos, avval /start buyrug'i orqali ro'yxatdan o'ting.")
        return
    await place_order(message, message.from_user, user, db, bot, config)
