import asyncio
import html
import logging
import re
from aiogram import Router, F
from aiogram.dispatcher.event.bases import SkipHandler
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from controlpribor_bot.channel_import import DEFAULT_CHANNEL, default_media_dir, import_channel
from controlpribor_bot.config import Config
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.handlers.catalog import invalidate_photo_cache
from controlpribor_bot.keyboards.default_kb import MAIN_MENU_TEXTS
from controlpribor_bot.keyboards.admin_kb import (
    get_admin_main_kb,
    get_admin_products_kb,
    get_admin_brands_kb,
    get_admin_categories_kb,
    get_brands_page_kb,
    get_categories_page_kb,
    get_brand_admin_card_kb,
    get_category_admin_card_kb,
    get_picker_kb,
    get_product_admin_actions_kb,
    get_confirm_delete_kb,
    get_cancel_or_skip_kb,
)

admin_router = Router(name="admin_router")
logger = logging.getLogger(__name__)
# Kanal importi bir vaqtda faqat bitta ishlaydi
_import_lock = asyncio.Lock()


# --- FSM Holatlari ---
class AdminBrandStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_new_name = State()


class AdminCategoryStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_brand = State()
    waiting_for_new_name = State()
    waiting_for_new_brand = State()


class AdminAddProductStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_brand = State()
    waiting_for_category = State()
    waiting_for_price = State()
    waiting_for_image = State()
    waiting_for_description = State()


class AdminSearchProductStates(StatesGroup):
    waiting_for_query = State()


class AdminEditProductStates(StatesGroup):
    waiting_for_price = State()
    waiting_for_name = State()
    waiting_for_desc = State()
    waiting_for_image = State()
    waiting_for_brand = State()
    waiting_for_category = State()


ADMIN_STATE_GROUPS = (
    AdminBrandStates,
    AdminCategoryStates,
    AdminAddProductStates,
    AdminSearchProductStates,
    AdminEditProductStates,
)

# Asosiy menyu tugmalari va /buyruqlar FSM holatida ma'lumot sifatida qabul qilinmaydi
IS_MENU = F.text.in_(MAIN_MENU_TEXTS) | F.text.startswith("/")
NOT_MENU = ~IS_MENU

# Sahifali tanlov turlari: tur -> (manba, tanlov prefiksi, "tanlanmagan" tugmasi matni)
PICKERS = {
    "cb": ("brands", "admin_cat_setbrand_", "🚫 Brendsiz saqlash"),
    "kb": ("brands", "admin_catedit_b_", "🚫 Brendsiz (umumiy)"),
    "pb": ("brands", "admin_prod_b_", "🚫 Brendsiz"),
    "pc": ("categories", "admin_prod_c_", "🚫 Kategoriyasiz"),
    "eb": ("brands", "admin_prod_setb_", "🚫 Brendsiz"),
    "ec": ("categories", "admin_prod_setc_", "🚫 Kategoriyasiz"),
}


def slugify(text: str) -> str:
    """Nomdan slug yaratish."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text or "brand"


def esc(value) -> str:
    """Matnni HTML xabar uchun xavfsiz qilish."""
    return html.escape(str(value)) if value is not None else ""


def extract_image(message: Message):
    """Xabardan rasm olish: Telegram file_id (token saqlanmaydi) yoki URL."""
    if message.photo:
        return message.photo[-1].file_id
    if message.text and (message.text.startswith("http://") or message.text.startswith("https://")):
        return message.text.strip()
    return None


async def build_picker(db: DatabaseManager, kind: str, page: int = 1) -> InlineKeyboardMarkup:
    source, prefix, none_text = PICKERS[kind]
    items = await db.get_brands() if source == "brands" else await db.get_all_categories()
    return get_picker_kb(items, kind=kind, pick_prefix=prefix, none_text=none_text, page=page)


# --- FSM Bekor qilish va O'tkazib yuborish ---
@admin_router.callback_query(F.data == "admin_fsm_cancel")
async def cancel_fsm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Amal bekor qilindi.")
    await callback.message.edit_text(
        "⚙️ <b>Admin boshqaruv paneli:</b>\nKerakli bo'limni tanlang:",
        reply_markup=get_admin_main_kb(),
        parse_mode="HTML",
    )


@admin_router.callback_query(F.data.startswith("admin_pick_"))
async def picker_page(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    _, _, kind, page = callback.data.split("_")
    if kind not in PICKERS:
        await callback.answer()
        return

    await callback.message.edit_reply_markup(reply_markup=await build_picker(db, kind, int(page)))
    await callback.answer()


# --- Asosiy Kirish ---
@admin_router.message(Command("admin"))
@admin_router.message(F.text == "⚙️ Admin panel")
async def show_admin_panel(message: Message, config: Config, state: FSMContext):
    if not config.is_admin(message.from_user.id):
        await message.answer("⛔️ Kechirasiz, sizda admin huquqi yo'q.")
        return

    await state.clear()
    await message.answer(
        "👑 <b>ASF Distribution — Admin boshqaruv paneli</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_admin_main_kb(),
        parse_mode="HTML",
    )


@admin_router.message(StateFilter(*ADMIN_STATE_GROUPS), IS_MENU)
async def leave_admin_fsm_on_menu(message: Message, state: FSMContext):
    """Admin ma'lumot kiritayotganda menyu tugmasi yoki buyruq bosilsa — amalni bekor qilib, tugmani o'z ishiga o'tkazish.

    Admin holat handlerlari NOT_MENU filtri bilan bu xabarni o'tkazib yuboradi, u boshqa routerlarga yetib boradi.
    """
    await state.clear()
    raise SkipHandler()


@admin_router.callback_query(F.data == "admin_back_main")
async def back_to_admin_main(callback: CallbackQuery, config: Config, state: FSMContext):
    if not config.is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        "👑 <b>ASF Distribution — Admin boshqaruv paneli</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:",
        reply_markup=get_admin_main_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_close")
async def close_admin_panel(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Admin panel yopildi.")


# --- Statistika ---
@admin_router.callback_query(F.data == "admin_stats")
async def show_admin_stats(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    stats = await db.get_stats()
    text = (
        "📊 <b>ASF Distribution — Do'kon Statistikasi</b>\n\n"
        f"👥 <b>Foydalanuvchilar:</b> {stats['users']:,} ta\n"
        f"📦 <b>Mahsulotlar:</b> {stats['products']:,} ta\n"
        f"🏷 <b>Brendlar:</b> {stats['brands']:,} ta\n"
        f"📁 <b>Kategoriyalar:</b> {stats['categories']:,} ta\n"
        f"🛍 <b>Buyurtmalar:</b> {stats['orders']:,} ta\n"
    ).replace(",", " ")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_back_main")]]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


# --- Telegram kanalidan import ---
@admin_router.callback_query(F.data == "admin_import_channel")
async def run_channel_import(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return
    if _import_lock.locked():
        await callback.answer("Import allaqachon ketmoqda, kuting...", show_alert=True)
        return

    await callback.answer()
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Admin menyusiga qaytish", callback_data="admin_back_main")]]
    )

    async def progress(text: str) -> None:
        try:
            await callback.message.edit_text(f"📥 <b>Import:</b> {esc(text)}", parse_mode="HTML")
        except Exception:
            pass

    async with _import_lock:
        await progress(f"@{DEFAULT_CHANNEL} kanali o'qilmoqda... Bu bir necha daqiqa vaqt olishi mumkin.")
        try:
            result = await import_channel(db, default_media_dir(config.db_path), progress=progress)
        except Exception as e:
            logger.exception("Kanal importida xatolik")
            await callback.message.edit_text(
                f"❌ <b>Import xatosi:</b> {esc(e)}", reply_markup=back_kb, parse_mode="HTML"
            )
            return

    text = (
        f"✅ <b>@{DEFAULT_CHANNEL} kanalidan import tugadi!</b>\n\n"
        f"🆕 Yangi tovarlar: <b>{result.created}</b> ta\n"
        f"🔄 Yangilangan (narx/tavsif): <b>{result.updated}</b> ta\n"
        f"🖼 Yuklangan rasmlar: <b>{result.images}</b> ta\n"
        f"⏭ Tovar bo'lmagan postlar: {result.skipped} ta"
    )
    review = result.needs_review
    if review:
        names = "\n".join(f"• {esc(p.name)} (#{p.post_id})" for p in review[:10])
        text += f"\n\n⚠️ <b>Nomi yoki kategoriyasini tekshiring ({len(review)} ta):</b>\n{names}"
    await callback.message.edit_text(text, reply_markup=back_kb, parse_mode="HTML")


# ==========================================
# 🏷 BRENDLAR BOSHQARUVI
# ==========================================
@admin_router.callback_query(F.data == "admin_brands")
async def show_admin_brands_menu(callback: CallbackQuery, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "🏷 <b>Brendlar boshqaruvi:</b>\n\n"
        "Yangi brend qo'shishingiz yoki mavjudlarini tahrirlashingiz/o'chirishingiz mumkin:",
        reply_markup=get_admin_brands_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_brand_add")
async def start_add_brand(callback: CallbackQuery, state: FSMContext, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await state.set_state(AdminBrandStates.waiting_for_name)
    await callback.message.edit_text(
        "🏷 <b>Yangi brend nomini kiriting:</b>\n"
        "<i>(Masalan: Schneider Electric, Siemens, Chint)</i>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminBrandStates.waiting_for_name, NOT_MENU)
async def process_brand_name(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    brand_name = message.text.strip() if message.text else ""
    if len(brand_name) < 2:
        await message.answer("⚠️ Brend nomi kamida 2 ta belgidan iborat bo'lishi kerak!")
        return

    slug = slugify(brand_name)
    existing = await db.find_brand(brand_name, slug)
    if existing:
        await message.answer(
            f"⚠️ «{esc(existing.name)}» brendi allaqachon mavjud. Boshqa nom kiriting:",
            reply_markup=get_cancel_or_skip_kb(can_skip=False),
            parse_mode="HTML",
        )
        return

    brand = await db.add_brand(name=brand_name, slug=slug)
    await state.clear()

    await message.answer(
        f"✅ <b>Brend muvaffaqiyatli qo'shildi!</b>\n\n"
        f"🏷 <b>Nomi:</b> {esc(brand.name)}\n"
        f"🔗 <b>Slug:</b> {esc(brand.slug)}",
        reply_markup=get_admin_brands_kb(),
        parse_mode="HTML",
    )


@admin_router.callback_query(F.data.startswith("admin_brand_list_"))
async def list_admin_brands(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    page = int(callback.data.split("_")[-1])
    brands = await db.get_brands()
    per_page = 8
    total_pages = max(1, (len(brands) + per_page - 1) // per_page)
    paged_brands = brands[(page - 1) * per_page : page * per_page]

    if not paged_brands:
        await callback.message.edit_text(
            "🏷 Hozircha birorta ham brend mavjud emas.",
            reply_markup=get_admin_brands_kb(),
        )
        await callback.answer()
        return

    kb = get_brands_page_kb(paged_brands, page, total_pages)
    await callback.message.edit_text(
        f"🏷 <b>Barcha brendlar ({len(brands)} ta):</b>\n"
        f"Tahrirlash uchun brend nomini, o'chirish uchun 🗑 tugmasini bosing:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


async def show_brand_admin_card(message_or_callback, db: DatabaseManager, brand):
    """Brend kartasini admin menyusi bilan chiqarish."""
    prod_count = await db.count_products(brand_id=brand.id)
    cat_count = await db.count_categories_of_brand(brand.id)
    text = (
        f"🏷 <b>{esc(brand.name)}</b>\n\n"
        f"🔗 <b>Slug:</b> {esc(brand.slug)}\n"
        f"📦 <b>Mahsulotlar:</b> {prod_count} ta\n"
        f"📁 <b>Kategoriyalar:</b> {cat_count} ta\n"
        f"🆔 <b>ID:</b> #{brand.id}"
    )
    kb = get_brand_admin_card_kb(brand.id)
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=kb, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("admin_brand_view_"))
async def admin_view_brand(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    brand = await db.get_brand_by_id(int(callback.data.split("_")[-1]))
    if not brand:
        await callback.answer("Brend topilmadi!", show_alert=True)
        return

    await show_brand_admin_card(callback, db, brand)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_brand_rename_"))
async def start_rename_brand(callback: CallbackQuery, state: FSMContext, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await state.set_state(AdminBrandStates.waiting_for_new_name)
    await state.update_data(edit_brand_id=int(callback.data.split("_")[-1]))
    await callback.message.edit_text(
        "✏️ <b>Brendning yangi nomini kiriting:</b>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminBrandStates.waiting_for_new_name, NOT_MENU)
async def process_brand_new_name(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    new_name = message.text.strip() if message.text else ""
    if len(new_name) < 2:
        await message.answer("⚠️ Brend nomi kamida 2 ta belgidan iborat bo'lishi kerak!")
        return

    data = await state.get_data()
    try:
        brand = await db.update_brand(data["edit_brand_id"], name=new_name, slug=slugify(new_name))
    except ValueError:
        await message.answer(
            "⚠️ Bunday nomli brend allaqachon mavjud. Boshqa nom kiriting:",
            reply_markup=get_cancel_or_skip_kb(can_skip=False),
        )
        return
    await state.clear()

    if not brand:
        await message.answer("⚠️ Brend topilmadi!", reply_markup=get_admin_brands_kb())
        return

    await message.answer("✅ <b>Brend nomi yangilandi!</b>", parse_mode="HTML")
    await show_brand_admin_card(message, db, brand)


@admin_router.callback_query(F.data.startswith("admin_brand_del_"))
async def confirm_delete_brand(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    brand_id = int(callback.data.split("_")[-1])
    brand = await db.get_brand_by_id(brand_id)
    if not brand:
        await callback.answer("Brend topilmadi!", show_alert=True)
        return

    await callback.message.edit_text(
        f"⚠️ <b>Haqiqatan ham «{esc(brand.name)}» brendini o'chirmoqchimisiz?</b>\n\n"
        "<i>Eslatma: Bu brendga biriktirilgan mahsulotlar o'chirilmaydi, ularning brend maydoni bo'shatiladi.</i>",
        reply_markup=get_confirm_delete_kb(target_type="brand", target_id=brand_id),
        parse_mode="HTML",
    )
    await callback.answer()


# ==========================================
# 📁 KATEGORIYALAR BOSHQARUVI
# ==========================================
@admin_router.callback_query(F.data == "admin_categories")
async def show_admin_categories_menu(callback: CallbackQuery, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "📁 <b>Kategoriyalar boshqaruvi:</b>\n\n"
        "Yangi kategoriya qo'shishingiz yoki mavjudlarini tahrirlashingiz/o'chirishingiz mumkin:",
        reply_markup=get_admin_categories_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.callback_query(F.data == "admin_cat_add")
async def start_add_category(callback: CallbackQuery, state: FSMContext, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await state.set_state(AdminCategoryStates.waiting_for_name)
    await callback.message.edit_text(
        "📁 <b>Yangi kategoriya nomini kiriting:</b>\n"
        "<i>(Masalan: AKFIX, CHINT, Metall shitlar, Instrumentlar)</i>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminCategoryStates.waiting_for_name, NOT_MENU)
async def process_category_name(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    cat_name = message.text.strip() if message.text else ""
    if len(cat_name) < 2:
        await message.answer("⚠️ Kategoriya nomi kamida 2 ta belgidan iborat bo'lishi kerak!")
        return

    existing = await db.find_category(cat_name)
    if existing:
        await message.answer(
            f"⚠️ «{esc(existing.name)}» kategoriyasi allaqachon mavjud. Boshqa nom kiriting:",
            reply_markup=get_cancel_or_skip_kb(can_skip=False),
            parse_mode="HTML",
        )
        return

    await state.update_data(cat_name=cat_name)
    await state.set_state(AdminCategoryStates.waiting_for_brand)
    await message.answer(
        f"📁 Kategoriya nomi: <b>{esc(cat_name)}</b>\n\n"
        "Ushbu kategoriya qaysi brendga tegishli? Kerakli brendni tanlang yoki 'Brendsiz' tugmasini bosing:",
        reply_markup=await build_picker(db, "cb"),
        parse_mode="HTML",
    )


@admin_router.callback_query(AdminCategoryStates.waiting_for_brand, F.data.startswith("admin_cat_setbrand_"))
async def process_category_brand(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    brand_id_raw = int(callback.data.split("_")[-1])
    brand_id = brand_id_raw if brand_id_raw > 0 else None

    data = await state.get_data()
    cat = await db.add_category(name=data.get("cat_name"), brand_id=brand_id)
    await state.clear()

    cat = await db.get_category_by_id(cat.id)
    await callback.message.edit_text(
        f"✅ <b>Kategoriya muvaffaqiyatli qo'shildi!</b>\n\n"
        f"📁 <b>Nomi:</b> {esc(cat.name)}\n"
        f"🏷 <b>Brend:</b> {esc(cat.brand.name) if cat.brand else 'Umumiy'}",
        reply_markup=get_admin_categories_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_cat_list_"))
async def list_admin_categories(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    page = int(callback.data.split("_")[-1])
    categories = await db.get_all_categories()
    per_page = 8
    total_pages = max(1, (len(categories) + per_page - 1) // per_page)
    paged_cats = categories[(page - 1) * per_page : page * per_page]

    if not paged_cats:
        await callback.message.edit_text(
            "📁 Hozircha kategoriyalar mavjud emas.",
            reply_markup=get_admin_categories_kb(),
        )
        await callback.answer()
        return

    kb = get_categories_page_kb(paged_cats, page, total_pages)
    await callback.message.edit_text(
        f"📁 <b>Barcha kategoriyalar ({len(categories)} ta):</b>\n"
        f"Tahrirlash uchun kategoriya nomini, o'chirish uchun 🗑 tugmasini bosing:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


async def show_category_admin_card(message_or_callback, db: DatabaseManager, cat):
    """Kategoriya kartasini admin menyusi bilan chiqarish."""
    prod_count = await db.count_products(category_id=cat.id)
    text = (
        f"📁 <b>{esc(cat.name)}</b>\n\n"
        f"🏷 <b>Brend:</b> {esc(cat.brand.name) if cat.brand else 'Umumiy'}\n"
        f"📦 <b>Mahsulotlar:</b> {prod_count} ta\n"
        f"🆔 <b>ID:</b> #{cat.id}"
    )
    kb = get_category_admin_card_kb(cat.id)
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=kb, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("admin_cat_view_"))
async def admin_view_category(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    cat = await db.get_category_by_id(int(callback.data.split("_")[-1]))
    if not cat:
        await callback.answer("Kategoriya topilmadi!", show_alert=True)
        return

    await show_category_admin_card(callback, db, cat)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin_cat_rename_"))
async def start_rename_category(callback: CallbackQuery, state: FSMContext, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await state.set_state(AdminCategoryStates.waiting_for_new_name)
    await state.update_data(edit_cat_id=int(callback.data.split("_")[-1]))
    await callback.message.edit_text(
        "✏️ <b>Kategoriyaning yangi nomini kiriting:</b>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminCategoryStates.waiting_for_new_name, NOT_MENU)
async def process_category_new_name(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    new_name = message.text.strip() if message.text else ""
    if len(new_name) < 2:
        await message.answer("⚠️ Kategoriya nomi kamida 2 ta belgidan iborat bo'lishi kerak!")
        return

    data = await state.get_data()
    try:
        cat = await db.update_category_fields(data["edit_cat_id"], name=new_name)
    except ValueError:
        await message.answer(
            "⚠️ Bunday nomli kategoriya allaqachon mavjud. Boshqa nom kiriting:",
            reply_markup=get_cancel_or_skip_kb(can_skip=False),
        )
        return
    await state.clear()

    if not cat:
        await message.answer("⚠️ Kategoriya topilmadi!", reply_markup=get_admin_categories_kb())
        return

    await message.answer("✅ <b>Kategoriya nomi yangilandi!</b>", parse_mode="HTML")
    await show_category_admin_card(message, db, cat)


@admin_router.callback_query(F.data.startswith("admin_cat_chbrand_"))
async def start_change_category_brand(callback: CallbackQuery, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await state.set_state(AdminCategoryStates.waiting_for_new_brand)
    await state.update_data(edit_cat_id=int(callback.data.split("_")[-1]))
    await callback.message.edit_text(
        "🏷 <b>Kategoriya uchun yangi brendni tanlang:</b>",
        reply_markup=await build_picker(db, "kb"),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.callback_query(AdminCategoryStates.waiting_for_new_brand, F.data.startswith("admin_catedit_b_"))
async def process_category_new_brand(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    brand_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    cat = await db.update_category_fields(data["edit_cat_id"], brand_id=brand_id if brand_id > 0 else None)
    await state.clear()

    if not cat:
        await callback.answer("Kategoriya topilmadi!", show_alert=True)
        return

    await callback.answer("✅ Brend yangilandi!")
    await show_category_admin_card(callback, db, cat)


@admin_router.callback_query(F.data.startswith("admin_cat_del_"))
async def confirm_delete_category(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    cat_id = int(callback.data.split("_")[-1])
    cat = await db.get_category_by_id(cat_id)
    if not cat:
        await callback.answer("Kategoriya topilmadi!", show_alert=True)
        return

    await callback.message.edit_text(
        f"⚠️ <b>Haqiqatan ham «{esc(cat.name)}» kategoriyasini o'chirmoqchimisiz?</b>\n\n"
        "<i>Eslatma: Ushbu kategoriyadagi mahsulotlar o'chirilmaydi, ularning kategoriya maydoni bo'shatiladi.</i>",
        reply_markup=get_confirm_delete_kb(target_type="cat", target_id=cat_id),
        parse_mode="HTML",
    )
    await callback.answer()


# ==========================================
# 📦 MAHSULOTLAR BOSHQARUVI
# ==========================================
@admin_router.callback_query(F.data == "admin_products")
async def show_admin_products_menu(callback: CallbackQuery, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "📦 <b>Mahsulotlar boshqaruvi:</b>\n\n"
        "Yangi mahsulot qo'shish yoki mavjudlarini qidirib tahrirlash/o'chirish:",
        reply_markup=get_admin_products_kb(),
        parse_mode="HTML",
    )
    await callback.answer()


# --- Yangi mahsulot qo'shish FSM ---
@admin_router.callback_query(F.data == "admin_prod_add")
async def start_add_product(callback: CallbackQuery, state: FSMContext, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await state.set_state(AdminAddProductStates.waiting_for_name)
    await callback.message.edit_text(
        "📦 <b>1-qadam: Mahsulot nomini kiriting:</b>\n"
        "<i>(Masalan: Fluke 107 raqamli multimetr)</i>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminAddProductStates.waiting_for_name, NOT_MENU)
async def process_prod_name(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    name = message.text.strip() if message.text else ""
    if len(name) < 2:
        await message.answer("⚠️ Mahsulot nomi kamida 2 ta belgidan iborat bo'lishi kerak!")
        return

    # Bir xil nomli tovar ustiga jimgina yozilib ketmasligi uchun
    existing = await db.get_product_by_name(name)
    if existing:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📦 Mavjud tovarni ochish", callback_data=f"admin_prod_view_{existing.id}")],
                [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_fsm_cancel")],
            ]
        )
        await message.answer(
            f"⚠️ «{esc(existing.name)}» nomli tovar allaqachon mavjud (ID #{existing.id}).\n"
            "Boshqa nom kiriting yoki mavjud tovarni tahrirlang:",
            reply_markup=kb,
            parse_mode="HTML",
        )
        return

    await state.update_data(name=name)
    await state.set_state(AdminAddProductStates.waiting_for_brand)
    await message.answer(
        f"🏷 <b>2-qadam: Mahsulot brendini tanlang:</b>\nNomi: <b>{esc(name)}</b>",
        reply_markup=await build_picker(db, "pb"),
        parse_mode="HTML",
    )


@admin_router.callback_query(AdminAddProductStates.waiting_for_brand, F.data.startswith("admin_prod_b_"))
async def process_prod_brand(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    brand_id = int(callback.data.split("_")[-1])
    await state.update_data(brand_id=brand_id if brand_id > 0 else None)

    await state.set_state(AdminAddProductStates.waiting_for_category)
    await callback.message.edit_text(
        "📁 <b>3-qadam: Mahsulot kategoriyasini tanlang:</b>",
        reply_markup=await build_picker(db, "pc"),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.callback_query(AdminAddProductStates.waiting_for_category, F.data.startswith("admin_prod_c_"))
async def process_prod_category(callback: CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[-1])
    await state.update_data(category_id=cat_id if cat_id > 0 else None)

    await state.set_state(AdminAddProductStates.waiting_for_price)
    await callback.message.edit_text(
        "💰 <b>4-qadam: Mahsulot narxini kiriting:</b>\n"
        "<i>(Masalan: 1 500 000 so'm yoki Kelishilgan holda)</i>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminAddProductStates.waiting_for_price, NOT_MENU)
async def process_prod_price(message: Message, state: FSMContext, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    price = message.text.strip() if message.text else "Kelishilgan holda"
    await state.update_data(price=price)

    await state.set_state(AdminAddProductStates.waiting_for_image)
    await message.answer(
        "🖼 <b>5-qadam: Mahsulot rasmini yuboring:</b>\n"
        "<i>(Rasm faylini yuborishingiz, rasm URL manzilini yozishingiz yoki 'O'tkazib yuborish' tugmasini bosishingiz mumkin)</i>",
        reply_markup=get_cancel_or_skip_kb(can_skip=True),
        parse_mode="HTML",
    )


@admin_router.callback_query(AdminAddProductStates.waiting_for_image, F.data == "admin_fsm_skip")
async def skip_prod_image(callback: CallbackQuery, state: FSMContext):
    await state.update_data(image_url=None)
    await state.set_state(AdminAddProductStates.waiting_for_description)
    await callback.message.edit_text(
        "📝 <b>6-qadam: Mahsulot tavsifini (xususiyatlarini) kiriting:</b>\n"
        "<i>(Yoki 'O'tkazib yuborish' tugmasini bosing)</i>",
        reply_markup=get_cancel_or_skip_kb(can_skip=True),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminAddProductStates.waiting_for_image, NOT_MENU)
async def process_prod_image_msg(message: Message, state: FSMContext, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    await state.update_data(image_url=extract_image(message))
    await state.set_state(AdminAddProductStates.waiting_for_description)
    await message.answer(
        "📝 <b>6-qadam: Mahsulot tavsifini (xususiyatlarini) kiriting:</b>\n"
        "<i>(Yoki 'O'tkazib yuborish' tugmasini bosing)</i>",
        reply_markup=get_cancel_or_skip_kb(can_skip=True),
        parse_mode="HTML",
    )


async def finish_add_product(state: FSMContext, db: DatabaseManager, description):
    data = await state.get_data()
    product = await db.add_product(
        name=data["name"],
        price=data.get("price", "Kelishilgan holda"),
        brand_id=data.get("brand_id"),
        category_id=data.get("category_id"),
        image_url=data.get("image_url"),
        description=description,
    )
    await state.clear()
    invalidate_photo_cache(product.id)
    return (
        f"🎉 <b>Mahsulot muvaffaqiyatli qo'shildi!</b>\n\n"
        f"📦 <b>Nomi:</b> {esc(product.name)}\n"
        f"💰 <b>Narxi:</b> {esc(product.price)}\n"
        f"🆔 <b>ID:</b> #{product.id}\n"
        f"📝 <b>Tavsif:</b> {esc(description) if description else 'Kiritilmagan'}"
    ), get_product_admin_actions_kb(product.id)


@admin_router.callback_query(AdminAddProductStates.waiting_for_description, F.data == "admin_fsm_skip")
async def skip_prod_description(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    text, kb = await finish_add_product(state, db, description=None)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@admin_router.message(AdminAddProductStates.waiting_for_description, NOT_MENU)
async def process_prod_description_msg(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    desc = message.text.strip() if message.text else None
    text, kb = await finish_add_product(state, db, description=desc)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


# --- Mahsulot qidirish va boshqarish ---
@admin_router.callback_query(F.data == "admin_prod_search")
async def start_search_product(callback: CallbackQuery, state: FSMContext, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await state.set_state(AdminSearchProductStates.waiting_for_query)
    await callback.message.edit_text(
        "🔍 <b>Tahrirlash yoki o'chirish uchun mahsulot nomini yoki modelini kiriting:</b>\n"
        "<i>(Masalan: Fluke, multimetr, relé yoki tovar ID raqami)</i>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminSearchProductStates.waiting_for_query, NOT_MENU)
async def process_search_query(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    query = message.text.strip() if message.text else ""
    await state.clear()

    # Agar raqam kiritilgan bo'lsa, avval to'g'ridan-to'g'ri ID bo'yicha tekshiramiz
    if query.isdigit():
        prod_by_id = await db.get_product_by_id(int(query))
        if prod_by_id:
            await show_product_admin_card(message, prod_by_id)
            return

    products, total = await db.search_products(query, page=1, limit=10)
    if not products:
        await message.answer(
            f"🔍 <i>'{esc(query)}'</i> bo'yicha hech qanday mahsulot topilmadi.",
            reply_markup=get_admin_products_kb(),
            parse_mode="HTML",
        )
        return

    keyboard = []
    for p in products:
        keyboard.append([InlineKeyboardButton(text=f"📦 {p.name[:35]}", callback_data=f"admin_prod_view_{p.id}")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_products")])

    await message.answer(
        f"🔍 <b>Qidiruv natijalari ({total} ta topildi):</b>\n"
        f"Boshqarish uchun mahsulotni tanlang:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML",
    )


async def show_product_admin_card(message_or_callback, product):
    """Mahsulot kartasini admin menyusi bilan chiqarish."""
    desc = product.description or "Tavsif kiritilmagan."
    brand_name = product.brand.name if product.brand else "Mavjud emas"
    cat_name = product.category.name if product.category else "Mavjud emas"

    text = (
        f"📦 <b>{esc(product.name)}</b>\n\n"
        f"🏷 <b>Brend:</b> {esc(brand_name)}\n"
        f"📁 <b>Kategoriya:</b> {esc(cat_name)}\n"
        f"💰 <b>Narxi:</b> {esc(product.price)}\n"
        f"🖼 <b>Rasm:</b> {'✅' if product.image_url else '❌'}\n"
        f"🆔 <b>ID:</b> #{product.id}\n\n"
        f"📝 <b>Tavsif:</b>\n{esc(desc[:500])}"
    )
    kb = get_product_admin_actions_kb(product.id)
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await message_or_callback.answer(text, reply_markup=kb, parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("admin_prod_view_"))
async def admin_view_product(callback: CallbackQuery, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split("_")[-1])
    product = await db.get_product_by_id(prod_id)
    if not product:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    await state.clear()
    await show_product_admin_card(callback, product)
    await callback.answer()


# --- Mahsulotni tahrirlash amallari ---
@admin_router.callback_query(F.data.startswith("admin_prod_edit_price_"))
async def start_edit_price(callback: CallbackQuery, state: FSMContext, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split("_")[-1])
    await state.set_state(AdminEditProductStates.waiting_for_price)
    await state.update_data(edit_prod_id=prod_id)
    await callback.message.edit_text(
        "💰 <b>Yangi narxni kiriting:</b>\n<i>(Masalan: 2 100 000 so'm yoki Kelishilgan holda)</i>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminEditProductStates.waiting_for_price, NOT_MENU)
async def process_new_price(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    new_price = message.text.strip() if message.text else "Kelishilgan holda"
    data = await state.get_data()
    updated = await db.update_product_fields(data["edit_prod_id"], price=new_price)
    await state.clear()

    await message.answer(f"✅ <b>Narx muvaffaqiyatli yangilandi:</b> {esc(new_price)}", parse_mode="HTML")
    if updated:
        await show_product_admin_card(message, updated)


@admin_router.callback_query(F.data.startswith("admin_prod_edit_name_"))
async def start_edit_name(callback: CallbackQuery, state: FSMContext, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split("_")[-1])
    await state.set_state(AdminEditProductStates.waiting_for_name)
    await state.update_data(edit_prod_id=prod_id)
    await callback.message.edit_text(
        "✏️ <b>Mahsulotning yangi nomini kiriting:</b>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminEditProductStates.waiting_for_name, NOT_MENU)
async def process_new_name(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    new_name = message.text.strip() if message.text else ""
    if len(new_name) < 2:
        await message.answer("⚠️ Nom kamida 2 ta belgidan iborat bo'lishi kerak!")
        return

    data = await state.get_data()
    prod_id = data["edit_prod_id"]
    existing = await db.get_product_by_name(new_name)
    if existing and existing.id != prod_id:
        await message.answer(
            f"⚠️ Bu nom boshqa tovarda (ID #{existing.id}) ishlatilgan. Boshqa nom kiriting:",
            reply_markup=get_cancel_or_skip_kb(can_skip=False),
        )
        return

    updated = await db.update_product_fields(prod_id, name=new_name)
    await state.clear()

    await message.answer("✅ <b>Mahsulot nomi yangilandi!</b>", parse_mode="HTML")
    if updated:
        await show_product_admin_card(message, updated)


@admin_router.callback_query(F.data.startswith("admin_prod_edit_desc_"))
async def start_edit_desc(callback: CallbackQuery, state: FSMContext, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split("_")[-1])
    await state.set_state(AdminEditProductStates.waiting_for_desc)
    await state.update_data(edit_prod_id=prod_id)
    await callback.message.edit_text(
        "📝 <b>Mahsulot uchun yangi tavsifni kiriting:</b>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminEditProductStates.waiting_for_desc, NOT_MENU)
async def process_new_desc(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    new_desc = message.text.strip() if message.text else ""
    data = await state.get_data()
    updated = await db.update_product_fields(data["edit_prod_id"], description=new_desc)
    await state.clear()

    await message.answer("✅ <b>Tavsif yangilandi!</b>", parse_mode="HTML")
    if updated:
        await show_product_admin_card(message, updated)


@admin_router.callback_query(F.data.startswith("admin_prod_edit_img_"))
async def start_edit_img(callback: CallbackQuery, state: FSMContext, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split("_")[-1])
    await state.set_state(AdminEditProductStates.waiting_for_image)
    await state.update_data(edit_prod_id=prod_id)
    await callback.message.edit_text(
        "🖼 <b>Mahsulot uchun yangi rasmni yuboring (yoki rasm URL manzilini yozing):</b>",
        reply_markup=get_cancel_or_skip_kb(can_skip=False),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.message(AdminEditProductStates.waiting_for_image, NOT_MENU)
async def process_new_img(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(message.from_user.id):
        return

    image_url = extract_image(message)
    if not image_url:
        await message.answer("⚠️ Iltimos, rasm yuboring yoki to'g'ri URL manzil kiriting!")
        return

    data = await state.get_data()
    prod_id = data["edit_prod_id"]
    updated = await db.update_product_fields(prod_id, image_url=image_url)
    invalidate_photo_cache(prod_id)
    await state.clear()

    await message.answer("✅ <b>Mahsulot rasmi muvaffaqiyatli yangilandi!</b>", parse_mode="HTML")
    if updated:
        await show_product_admin_card(message, updated)


@admin_router.callback_query(F.data.startswith("admin_prod_edit_brand_"))
async def start_edit_prod_brand(callback: CallbackQuery, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await state.set_state(AdminEditProductStates.waiting_for_brand)
    await state.update_data(edit_prod_id=int(callback.data.split("_")[-1]))
    await callback.message.edit_text(
        "🏷 <b>Mahsulot uchun yangi brendni tanlang:</b>",
        reply_markup=await build_picker(db, "eb"),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.callback_query(AdminEditProductStates.waiting_for_brand, F.data.startswith("admin_prod_setb_"))
async def process_new_prod_brand(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    brand_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    updated = await db.update_product_fields(data["edit_prod_id"], brand_id=brand_id if brand_id > 0 else None)
    await state.clear()

    if not updated:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    await callback.answer("✅ Brend yangilandi!")
    await show_product_admin_card(callback, updated)


@admin_router.callback_query(F.data.startswith("admin_prod_edit_cat_"))
async def start_edit_prod_category(callback: CallbackQuery, state: FSMContext, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    await state.set_state(AdminEditProductStates.waiting_for_category)
    await state.update_data(edit_prod_id=int(callback.data.split("_")[-1]))
    await callback.message.edit_text(
        "📁 <b>Mahsulot uchun yangi kategoriyani tanlang:</b>",
        reply_markup=await build_picker(db, "ec"),
        parse_mode="HTML",
    )
    await callback.answer()


@admin_router.callback_query(AdminEditProductStates.waiting_for_category, F.data.startswith("admin_prod_setc_"))
async def process_new_prod_category(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    cat_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    updated = await db.update_product_fields(data["edit_prod_id"], category_id=cat_id if cat_id > 0 else None)
    await state.clear()

    if not updated:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    await callback.answer("✅ Kategoriya yangilandi!")
    await show_product_admin_card(callback, updated)


@admin_router.callback_query(F.data.startswith("admin_prod_del_"))
async def confirm_delete_product(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    prod_id = int(callback.data.split("_")[-1])
    product = await db.get_product_by_id(prod_id)
    if not product:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    await callback.message.edit_text(
        f"⚠️ <b>Haqiqatan ham «{esc(product.name)}» mahsulotini o'chirmoqchimisiz?</b>\n\n"
        "<i>Eslatma: Ushbu amalni ortga qaytarib bo'lmaydi.</i>",
        reply_markup=get_confirm_delete_kb(target_type="product", target_id=prod_id),
        parse_mode="HTML",
    )
    await callback.answer()


# ==========================================
# 🗑 O'CHIRISHNI TASDIQLASH VA BEKOR QILISH
# ==========================================
@admin_router.callback_query(F.data.startswith("admin_confirm_del_"))
async def execute_delete(callback: CallbackQuery, db: DatabaseManager, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    parts = callback.data.split("_")
    target_type = parts[3]  # brand, cat, product
    target_id = int(parts[4])

    if target_type == "brand":
        await db.delete_brand(target_id)
        await callback.answer("Brend o'chirildi!", show_alert=True)
        await callback.message.edit_text(
            "✅ <b>Brend muvaffaqiyatli o'chirildi.</b>",
            reply_markup=get_admin_brands_kb(),
            parse_mode="HTML",
        )
    elif target_type == "cat":
        await db.delete_category(target_id)
        await callback.answer("Kategoriya o'chirildi!", show_alert=True)
        await callback.message.edit_text(
            "✅ <b>Kategoriya muvaffaqiyatli o'chirildi.</b>",
            reply_markup=get_admin_categories_kb(),
            parse_mode="HTML",
        )
    elif target_type == "product":
        await db.delete_product(target_id)
        invalidate_photo_cache(target_id)
        await callback.answer("Mahsulot o'chirildi!", show_alert=True)
        await callback.message.edit_text(
            "✅ <b>Mahsulot muvaffaqiyatli o'chirildi.</b>",
            reply_markup=get_admin_products_kb(),
            parse_mode="HTML",
        )


@admin_router.callback_query(F.data.startswith("admin_cancel_del_"))
async def cancel_delete(callback: CallbackQuery, config: Config):
    if not config.is_admin(callback.from_user.id):
        return

    target_type = callback.data.split("_")[-1]
    await callback.answer("O'chirish bekor qilindi.")
    if target_type == "brand":
        await callback.message.edit_text(
            "🏷 <b>Brendlar boshqaruvi:</b>",
            reply_markup=get_admin_brands_kb(),
            parse_mode="HTML",
        )
    elif target_type == "cat":
        await callback.message.edit_text(
            "📁 <b>Kategoriyalar boshqaruvi:</b>",
            reply_markup=get_admin_categories_kb(),
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(
            "📦 <b>Mahsulotlar boshqaruvi:</b>",
            reply_markup=get_admin_products_kb(),
            parse_mode="HTML",
        )
