import html
import re
from datetime import datetime
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery

from controlpribor_bot.config import Config
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.keyboards.inline_kb import get_cart_kb

cart_router = Router(name="cart_router")


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


@cart_router.callback_query(F.data == "checkout_order")
async def checkout_order_handler(callback: CallbackQuery, db: DatabaseManager, bot: Bot, config: Config):
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return

    items = await db.get_cart_items(user_id=user.id)
    if not items:
        await callback.answer("Savatchangiz bo'sh!", show_alert=True)
        return

    _, total_price = format_cart_message(items)

    # 1. Bazada buyurtma yaratish
    order = await db.create_order(
        user_id=user.id,
        total_price=total_price,
        items=items,
    )

    # 2. Xodimlar Telegram guruhiga buyurtma yuborish
    group_id = config.ORDER_GROUP_ID
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    order_lines = []
    for idx, itm in enumerate(items, start=1):
        order_lines.append(
            f"{idx}. {html.escape(itm['product_name'])} — {itm['quantity']} dona (Narxi: {html.escape(itm['price'])})"
        )

    items_block = "\n".join(order_lines)
    username = f"@{callback.from_user.username}" if callback.from_user.username else f"ID: {callback.from_user.id}"

    group_message = (
        f"🔔 <b>YANGI BUYURTMA #{order.id}</b>\n"
        f"👤 <b>Mijoz:</b> {html.escape(user.full_name)}\n"
        f"📞 <b>Telefon:</b> {html.escape(user.phone_number)}\n"
        f"💬 <b>Telegram:</b> {username}\n"
        f"────────────────────────────────\n"
        f"📦 <b>Mahsulotlar:</b>\n"
        f"{items_block}\n"
        f"────────────────────────────────\n"
        f"💰 <b>Jami:</b> {total_price}\n"
        f"⏰ <b>Vaqti:</b> {now_str}"
    )

    if group_id and group_id != 0:
        try:
            await bot.send_message(
                chat_id=group_id,
                text=group_message,
                parse_mode="HTML",
            )
        except Exception as e:
            # Agar guruh ID noto'g'ri bo'lsa yoki bot guruhda bo'lmasa, mijozga xatolik bermaymiz
            pass

    # 3. Savatchani tozalash
    await db.clear_cart(user_id=user.id)

    # 4. Mijozga javob
    await callback.message.delete()
    await callback.message.answer(
        f"✅ <b>Buyurtmangiz muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"🆔 <b>Buyurtma raqami:</b> #{order.id}\n"
        f"💰 <b>Summa:</b> {total_price}\n\n"
        f"Operatorimiz tez orada siz bilan bog'lanadi va yetkazib berish shartlarini kelishadi.\n"
        f"Xaridingiz uchun rahmat!",
        parse_mode="HTML",
    )
    await callback.answer()
