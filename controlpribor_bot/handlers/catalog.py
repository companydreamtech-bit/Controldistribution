import html
import math
from pathlib import Path
from typing import Optional, Union

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile

from controlpribor_bot.config import Config
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.handlers.start import NO_PHONE
from controlpribor_bot.keyboards.default_kb import LEGACY_CATALOG_BUTTONS, PRODUCTS_BUTTON, get_main_menu_kb
from controlpribor_bot.keyboards.inline_kb import (
    get_brands_kb,
    get_categories_kb,
    get_products_list_kb,
    get_product_detail_kb,
)

catalog_router = Router(name="catalog_router")
PER_PAGE = 6
# Tezkor rasm yuborish uchun Telegram file_id keshi
_PHOTO_CACHE = {}


PACKAGE_DIR = Path(__file__).resolve().parent.parent


def invalidate_photo_cache(product_id: int) -> None:
    """Admin rasmni yangilaganda yoki tovarni o'chirganda eski file_id ni tashlab yuborish."""
    _PHOTO_CACHE.pop(product_id, None)


def resolve_photo(image_url: Optional[str], db_path: str) -> Optional[Union[str, FSInputFile]]:
    """Rasm manbasi: URL / Telegram file_id o'zicha, kanal importidagi "media/..." esa lokal fayl.

    Lokal fayl avval baza papkasida (masalan Railway volume), keyin loyiha papkasida qidiriladi.
    """
    if not image_url:
        return None
    if not image_url.startswith("media/"):
        return image_url
    for base in (Path(db_path).resolve().parent, PACKAGE_DIR):
        path = base / image_url
        if path.is_file():
            return FSInputFile(path)
    return None


PRODUCTS_TITLE = "📦 <b>Tovarlar:</b>\n\nKerakli bo'limni tanlang:"


def shop_categories_kb(categories):
    """"📦 Tovarlar" bo'limlari: hammasi bitta sahifada, 2 ustunda."""
    return get_categories_kb(categories, brand_id=None, page=1, per_page=max(1, len(categories)), columns=2)


@catalog_router.message(F.text == PRODUCTS_BUTTON)
@catalog_router.message(F.text.in_(LEGACY_CATALOG_BUTTONS))
async def show_products_menu(message: Message, db: DatabaseManager, config: Config):
    if message.text in LEGACY_CATALOG_BUTTONS:
        # Eski klaviatura bilan kelgan foydalanuvchiga yangi menyuni beramiz
        await message.answer(
            "🔄 Menyu yangilandi: brendlar va kategoriyalar endi «📦 Tovarlar» bo'limida.",
            reply_markup=get_main_menu_kb(is_admin=config.is_admin(message.from_user.id)),
        )

    categories = await db.get_shop_categories()
    if not categories:
        await message.answer("Hozircha tovarlar mavjud emas.")
        return

    await message.answer(PRODUCTS_TITLE, reply_markup=shop_categories_kb(categories), parse_mode="HTML")


@catalog_router.callback_query(F.data.startswith("brands_page_"))
async def handle_brands_pagination(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer()
    page = int(callback.data.split("_")[-1])
    brands = await db.get_brands()
    await callback.message.edit_text(
        "🏷 <b>Asosiy brendlar:</b>\n\nKerakli brendni tanlang:",
        reply_markup=get_brands_kb(brands, page=page),
        parse_mode="HTML",
    )


@catalog_router.callback_query(F.data.startswith("allcats_page_"))
async def handle_all_categories_pagination(callback: CallbackQuery, db: DatabaseManager):
    # Eski xabarlardagi sahifa tugmalari uchun: endi barcha bo'limlar bitta sahifada
    await callback.answer()
    categories = await db.get_shop_categories()
    await callback.message.edit_text(PRODUCTS_TITLE, reply_markup=shop_categories_kb(categories), parse_mode="HTML")


@catalog_router.callback_query(F.data.startswith("cats_page_"))
async def handle_brand_categories_pagination(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer()
    parts = callback.data.split("_")
    brand_id = int(parts[2])
    page = int(parts[3])
    brand = await db.get_brand_by_id(brand_id)
    categories = await db.get_categories_by_brand(brand_id)
    brand_title = f"🏷 <b>{html.escape(brand.name)}</b> brendiga tegishli toifalar:" if brand else "Toifalar:"
    await callback.message.edit_text(
        f"{brand_title}\n\nBo'limni tanlang:",
        reply_markup=get_categories_kb(categories, brand_id=brand_id, page=page),
        parse_mode="HTML",
    )


@catalog_router.callback_query(F.data.startswith("brand_"))
async def handle_brand_click(callback: CallbackQuery, db: DatabaseManager):
    # Callback'ga faqat bir marta javob berish mumkin, shuning uchun alertdan oldin answer() chaqirilmaydi
    brand_id = int(callback.data.split("_")[1])
    brand = await db.get_brand_by_id(brand_id)
    if not brand:
        await callback.answer("Brend topilmadi!", show_alert=True)
        return

    categories = await db.get_categories_by_brand(brand_id)
    if categories:
        await callback.answer()
        await callback.message.edit_text(
            f"🏷 <b>{html.escape(brand.name)}</b> brendiga tegishli toifalar:\n\nBo'limni tanlang:",
            reply_markup=get_categories_kb(categories, brand_id=brand_id, page=1),
            parse_mode="HTML",
        )
    else:
        # Toifasi bo'lmasa, to'g'ridan-to'g'ri tovarlarni ko'rsatish
        products, total = await db.get_products_by_brand(brand_id, page=1, limit=PER_PAGE)
        total_pages = max(1, math.ceil(total / PER_PAGE))
        if not products:
            await callback.answer("Ushbu brendda hozircha tovarlar mavjud emas.", show_alert=True)
            return

        await callback.answer()
        await callback.message.edit_text(
            f"🏷 <b>{html.escape(brand.name)}</b> mahsulotlari ({total} ta):",
            reply_markup=get_products_list_kb(products, page=1, total_pages=total_pages, brand_id=brand_id),
            parse_mode="HTML",
        )


@catalog_router.callback_query(F.data.startswith("cat_"))
async def handle_category_click(callback: CallbackQuery, db: DatabaseManager):
    parts = callback.data.split("_")
    category_id = int(parts[1])
    brand_id = int(parts[2]) if len(parts) > 2 else None

    cat = await db.get_category_by_id(category_id)
    if not cat:
        await callback.answer("Toifa topilmadi!", show_alert=True)
        return

    products, total = await db.get_products_by_category(category_id, brand_id=brand_id, page=1, limit=PER_PAGE)
    total_pages = max(1, math.ceil(total / PER_PAGE))

    if not products:
        await callback.answer("Ushbu toifada tovarlar topilmadi.", show_alert=True)
        return

    await callback.answer()
    brand_name = ""
    if brand_id:
        brand = await db.get_brand_by_id(brand_id)
        if brand:
            brand_name = f" ({html.escape(brand.name)})"

    await callback.message.edit_text(
        f"📁 <b>{html.escape(cat.name)}</b>{brand_name} bo'limi tovarlari (Jami: {total} ta):\n\nKerakli mahsulotni tanlang:",
        reply_markup=get_products_list_kb(
            products, page=1, total_pages=total_pages, category_id=category_id, brand_id=brand_id
        ),
        parse_mode="HTML",
    )


@catalog_router.callback_query(F.data.startswith("prod_"))
async def handle_product_click(callback: CallbackQuery, db: DatabaseManager, config: Config):
    product_id = int(callback.data.split("_")[1])
    product = await db.get_product_by_id(product_id)
    if not product:
        await callback.answer("Tovar topilmadi!", show_alert=True)
        return
    await callback.answer()

    # Telegram rasm izohi (caption) 1024 belgidan oshmasligi uchun tavsifni qisqartiramiz
    desc = product.description or ""
    if len(desc) > 600:
        desc = desc[:600].rstrip() + "…"
    # Brend alohida bo'lim emas: kanaldan kelgan tovarda bo'lsa, ma'lumot sifatida ko'rsatiladi
    brand_line = f"🏷 <b>Brend:</b> {html.escape(product.brand.name)}\n" if product.brand else ""
    text = (
        f"📦 <b>{html.escape(product.name)}</b>\n\n"
        f"📁 <b>Bo'lim:</b> {html.escape(product.category.name) if product.category else 'Umumiy'}\n"
        f"{brand_line}"
        f"💰 <b>Narxi:</b> <code>{html.escape(product.price or '')}</code>\n\n"
        f"📝 <i>{html.escape(desc)}</i>"
    )
    caption = text

    kb = get_product_detail_kb(
        product_id=product.id,
        quantity=1,
        category_id=product.category_id,
        brand_id=product.brand_id,
        page=1,
    )

    # 1. Keshdagi Telegram file_id orqali tezkor ochish
    cached_file_id = _PHOTO_CACHE.get(product.id)
    if cached_file_id:
        try:
            await callback.message.delete()
            await callback.message.answer_photo(
                photo=cached_file_id,
                caption=caption,
                reply_markup=kb,
                parse_mode="HTML",
            )
            return
        except Exception:
            pass

    # 2. URL, Telegram file_id yoki lokal fayl orqali ochish va file_id ni keshga olish
    photo = resolve_photo(product.image_url, config.db_path)
    if photo:
        try:
            sent = await callback.message.answer_photo(
                photo=photo,
                caption=caption,
                reply_markup=kb,
                parse_mode="HTML",
            )
            if sent.photo:
                _PHOTO_CACHE[product.id] = sent.photo[-1].file_id
            try:
                await callback.message.delete()
            except Exception:
                pass
            return
        except Exception:
            pass

    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")


@catalog_router.callback_query(F.data.startswith("qty_minus_") | F.data.startswith("qty_plus_"))
async def handle_quantity_change(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer()
    parts = callback.data.split("_")
    action = parts[1]  # minus or plus
    product_id = int(parts[2])
    current_qty = int(parts[3])

    if action == "minus":
        new_qty = max(1, current_qty - 1)
    else:
        new_qty = min(999, current_qty + 1)

    if new_qty == current_qty:
        return

    product = await db.get_product_by_id(product_id)
    kb = get_product_detail_kb(
        product_id=product_id,
        quantity=new_qty,
        category_id=product.category_id if product else None,
        brand_id=product.brand_id if product else None,
    )
    await callback.message.edit_reply_markup(reply_markup=kb)


@catalog_router.callback_query(F.data.startswith("add_cart_"))
async def handle_add_to_cart(callback: CallbackQuery, db: DatabaseManager):
    parts = callback.data.split("_")
    product_id = int(parts[2])
    quantity = int(parts[3])

    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if not user:
        user, _ = await db.get_or_create_user(
            telegram_id=callback.from_user.id,
            full_name=callback.from_user.full_name or "Mijoz",
            phone_number=NO_PHONE,
        )

    await db.add_to_cart(user_id=user.id, product_id=product_id, quantity=quantity)
    await callback.answer(f"✅ {quantity} dona savatchaga qo'shildi!", show_alert=False)


@catalog_router.callback_query(F.data.startswith("prods_cat_") | F.data.startswith("prods_brand_"))
async def handle_products_pagination(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer()
    data = callback.data
    if "_brand_" in data and data.startswith("prods_cat_"):
        parts = data.split("_")
        category_id = int(parts[2])
        brand_id = int(parts[4])
        page = int(parts[6])
        products, total = await db.get_products_by_category(category_id, brand_id=brand_id, page=page, limit=PER_PAGE)
        cat = await db.get_category_by_id(category_id)
        brand = await db.get_brand_by_id(brand_id)
        brand_name = f" ({html.escape(brand.name)})" if brand else ""
        title = f"📁 <b>{html.escape(cat.name) if cat else 'Toifa'}</b>{brand_name} bo'limi tovarlari (Jami: {total} ta):"
    elif data.startswith("prods_cat_"):
        parts = data.split("_")
        category_id = int(parts[2])
        brand_id = None
        page = int(parts[4])
        products, total = await db.get_products_by_category(category_id, brand_id=None, page=page, limit=PER_PAGE)
        cat = await db.get_category_by_id(category_id)
        title = f"📁 <b>{html.escape(cat.name) if cat else 'Toifa'}</b> bo'limi tovarlari (Jami: {total} ta):"
    else:
        parts = data.split("_")
        category_id = None
        brand_id = int(parts[2])
        page = int(parts[4])
        products, total = await db.get_products_by_brand(brand_id, page=page, limit=PER_PAGE)
        brand = await db.get_brand_by_id(brand_id)
        title = f"🏷 <b>{html.escape(brand.name) if brand else 'Brend'}</b> mahsulotlari (Jami: {total} ta):"

    total_pages = max(1, math.ceil(total / PER_PAGE))
    kb = get_products_list_kb(
        products,
        page=page,
        total_pages=total_pages,
        category_id=category_id,
        brand_id=brand_id,
    )
    await callback.message.edit_text(title, reply_markup=kb, parse_mode="HTML")


@catalog_router.callback_query(F.data.startswith("back_prods_"))
async def handle_back_to_products_list(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer()
    data = callback.data
    try:
        await callback.message.delete()
    except Exception:
        pass

    if "_brand_" in data and data.startswith("back_prods_cat_"):
        parts = data.split("_")
        category_id = int(parts[3])
        brand_id = int(parts[5])
        page = int(parts[6])
        products, total = await db.get_products_by_category(category_id, brand_id=brand_id, page=page, limit=PER_PAGE)
        cat = await db.get_category_by_id(category_id)
        brand = await db.get_brand_by_id(brand_id)
        brand_name = f" ({html.escape(brand.name)})" if brand else ""
        title = f"📁 <b>{html.escape(cat.name) if cat else 'Toifa'}</b>{brand_name} bo'limi tovarlari (Jami: {total} ta):"
    elif data.startswith("back_prods_cat_"):
        parts = data.split("_")
        category_id = int(parts[3])
        brand_id = None
        page = int(parts[4])
        products, total = await db.get_products_by_category(category_id, brand_id=None, page=page, limit=PER_PAGE)
        cat = await db.get_category_by_id(category_id)
        title = f"📁 <b>{html.escape(cat.name) if cat else 'Toifa'}</b> bo'limi tovarlari (Jami: {total} ta):"
    else:
        parts = data.split("_")
        category_id = None
        brand_id = int(parts[3])
        page = int(parts[4])
        products, total = await db.get_products_by_brand(brand_id, page=page, limit=PER_PAGE)
        brand = await db.get_brand_by_id(brand_id)
        title = f"🏷 <b>{html.escape(brand.name) if brand else 'Brend'}</b> mahsulotlari (Jami: {total} ta):"

    total_pages = max(1, math.ceil(total / PER_PAGE))
    kb = get_products_list_kb(
        products,
        page=page,
        total_pages=total_pages,
        category_id=category_id,
        brand_id=brand_id,
    )
    await callback.message.answer(title, reply_markup=kb, parse_mode="HTML")


@catalog_router.callback_query(F.data.startswith("back_brand_cats_"))
async def back_to_brand_categories(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer()
    brand_id = int(callback.data.split("_")[-1])
    brand = await db.get_brand_by_id(brand_id)
    if not brand:
        # Brend o'chirilgan bo'lsa, brendlar ro'yxatiga qaytamiz
        brands = await db.get_brands()
        await callback.message.edit_text(
            "🏷 <b>Asosiy brendlar:</b>\n\nKerakli brendni tanlang:",
            reply_markup=get_brands_kb(brands, page=1),
            parse_mode="HTML",
        )
        return
    categories = await db.get_categories_by_brand(brand_id)
    await callback.message.edit_text(
        f"🏷 <b>{html.escape(brand.name)}</b> brendiga tegishli toifalar:\n\nBo'limni tanlang:",
        reply_markup=get_categories_kb(categories, brand_id=brand_id, page=1),
        parse_mode="HTML",
    )


@catalog_router.callback_query(F.data == "back_to_brands")
async def back_to_brands_list(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer()
    brands = await db.get_brands()
    await callback.message.edit_text(
        "🏷 <b>Asosiy brendlar:</b>\n\nKerakli brendni tanlang:",
        reply_markup=get_brands_kb(brands, page=1),
        parse_mode="HTML",
    )


@catalog_router.callback_query(F.data == "back_to_cats")
async def back_to_categories_list(callback: CallbackQuery, db: DatabaseManager):
    await callback.answer()
    categories = await db.get_shop_categories()
    await callback.message.edit_text(PRODUCTS_TITLE, reply_markup=shop_categories_kb(categories), parse_mode="HTML")


@catalog_router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()
