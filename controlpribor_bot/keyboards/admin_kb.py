from typing import Dict, List, Optional, Sequence, Tuple
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from controlpribor_bot.database.models import Category, Product
from controlpribor_bot.keyboards.icons import category_icon


def get_admin_main_kb() -> InlineKeyboardMarkup:
    """Admin asosiy boshqaruv menyusi (mijozdagi "📦 Tovarlar" tuzilishiga mos)."""
    keyboard = [
        [
            InlineKeyboardButton(text="📦 Mahsulotlar", callback_data="admin_products"),
            InlineKeyboardButton(text="📁 Kategoriyalar", callback_data="admin_categories"),
        ],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton(text="📥 Kanaldan import (@asfdistribution)", callback_data="admin_import_channel"),
        ],
        [
            InlineKeyboardButton(text="❌ Menyuni yopish", callback_data="admin_close"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_products_kb() -> InlineKeyboardMarkup:
    """Mahsulotlar bo'limi klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton(text="➕ Yangi mahsulot qo'shish", callback_data="admin_prod_add")],
        [InlineKeyboardButton(text="🔍 Mahsulot qidirish / Tahrirlash / O'chirish", callback_data="admin_prod_search")],
        [InlineKeyboardButton(text="📁 Bo'limlar bo'yicha ko'rish", callback_data="admin_cat_list_1")],
        [InlineKeyboardButton(text="⬅️ Admin menyusiga qaytish", callback_data="admin_back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_categories_kb() -> InlineKeyboardMarkup:
    """Kategoriyalar bo'limi klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton(text="📋 Barcha bo'limlar (mijozdagi tartibda)", callback_data="admin_cat_list_1")],
        [InlineKeyboardButton(text="➕ Yangi kategoriya qo'shish", callback_data="admin_cat_add")],
        [InlineKeyboardButton(text="⬅️ Admin menyusiga qaytish", callback_data="admin_back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _nav_row(prefix: str, page: int, total_pages: int) -> List[InlineKeyboardButton]:
    row = []
    if page > 1:
        row.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"{prefix}{page - 1}"))
    row.append(InlineKeyboardButton(text=f"📄 {page}/{max(1, total_pages)}", callback_data="noop"))
    if page < total_pages:
        row.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"{prefix}{page + 1}"))
    return row


def get_categories_page_kb(
    categories: List[Category], page: int, total_pages: int, counts: Dict[int, int]
) -> InlineKeyboardMarkup:
    """Kategoriyalar ro'yxati: nomi va tovarlar soni (bosilsa — kategoriya kartasi)."""
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{category_icon(c.name)} {c.name[:25]} ({counts.get(c.id, 0)})",
                callback_data=f"admin_cat_view_{c.id}",
            )
        ]
        for c in categories
    ]
    keyboard.append(_nav_row("admin_cat_list_", page, total_pages))
    keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_category_admin_card_kb(category_id: int) -> InlineKeyboardMarkup:
    """Tanlangan kategoriyani boshqarish klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton(text="📦 Tovarlarini ko'rish", callback_data=f"admin_cat_prods_{category_id}_1")],
        [InlineKeyboardButton(text="✏️ Nomini o'zgartirish", callback_data=f"admin_cat_rename_{category_id}")],
        [InlineKeyboardButton(text="🗑 Kategoriyani o'chirish", callback_data=f"admin_cat_del_{category_id}")],
        [InlineKeyboardButton(text="⬅️ Bo'limlar ro'yxatiga", callback_data="admin_cat_list_1")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_category_products_kb(
    products: List[Product], category_id: int, page: int, total_pages: int
) -> InlineKeyboardMarkup:
    """Kategoriyadagi tovarlar: bosilsa — tovarning admin kartasi."""
    keyboard = [
        [InlineKeyboardButton(text=f"📦 {p.name[:40]}", callback_data=f"admin_prod_view_{p.id}")]
        for p in products
    ]
    if total_pages > 1:
        keyboard.append(_nav_row(f"admin_cat_prods_{category_id}_", page, total_pages))
    keyboard.append([InlineKeyboardButton(text="⬅️ Kategoriyaga qaytish", callback_data=f"admin_cat_view_{category_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_product_admin_actions_kb(product_id: int, category_id: Optional[int] = None) -> InlineKeyboardMarkup:
    """Tanlangan mahsulotni boshqarish klaviaturasi."""
    back_row = [InlineKeyboardButton(text="⬅️ Mahsulotlar", callback_data="admin_products")]
    if category_id:
        back_row.insert(0, InlineKeyboardButton(text="📁 Bo'limiga", callback_data=f"admin_cat_prods_{category_id}_1"))
    keyboard = [
        [
            InlineKeyboardButton(text="✏️ Narxni o'zgartirish", callback_data=f"admin_prod_edit_price_{product_id}"),
            InlineKeyboardButton(text="✏️ Nomni o'zgartirish", callback_data=f"admin_prod_edit_name_{product_id}"),
        ],
        [
            InlineKeyboardButton(text="✏️ Tavsifni o'zgartirish", callback_data=f"admin_prod_edit_desc_{product_id}"),
            InlineKeyboardButton(text="🖼 Rasmni yangilash", callback_data=f"admin_prod_edit_img_{product_id}"),
        ],
        [
            InlineKeyboardButton(text="📁 Kategoriyani o'zgartirish", callback_data=f"admin_prod_edit_cat_{product_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 Mahsulotni o'chirish", callback_data=f"admin_prod_del_{product_id}"),
        ],
        back_row,
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_confirm_delete_kb(target_type: str, target_id: int) -> InlineKeyboardMarkup:
    """O'chirishni tasdiqlash klaviaturasi."""
    keyboard = [
        [
            InlineKeyboardButton(text="🗑 Ha, o'chirilsin", callback_data=f"admin_confirm_del_{target_type}_{target_id}"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"admin_cancel_del_{target_type}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_cancel_or_skip_kb(can_skip: bool = False) -> InlineKeyboardMarkup:
    """FSM jarayonida bekor qilish yoki o'tkazib yuborish."""
    keyboard = []
    row = []
    if can_skip:
        row.append(InlineKeyboardButton(text="⏭ O'tkazib yuborish", callback_data="admin_fsm_skip"))
    row.append(InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_fsm_cancel"))
    keyboard.append(row)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


PICKER_PER_PAGE = 10


def get_picker_kb(
    items: List,
    kind: str,
    pick_prefix: str,
    none_text: Optional[str],
    page: int = 1,
    extra_buttons: Sequence[Tuple[str, str]] = (),
) -> InlineKeyboardMarkup:
    """Brend yoki kategoriyani sahifalab tanlash klaviaturasi.

    Tanlov tugmasi: f"{pick_prefix}{id}" ("0" — tanlanmagan, none_text bo'lsa), sahifa tugmasi:
    f"admin_pick_{kind}_{page}". extra_buttons — (matn, callback_data) qo'shimcha tugmalar.
    """
    total_pages = max(1, (len(items) + PICKER_PER_PAGE - 1) // PICKER_PER_PAGE)
    page = min(max(1, page), total_pages)
    paged = items[(page - 1) * PICKER_PER_PAGE : page * PICKER_PER_PAGE]

    keyboard = []
    row = []
    for item in paged:
        row.append(InlineKeyboardButton(text=item.name[:30], callback_data=f"{pick_prefix}{item.id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    if total_pages > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="◀️", callback_data=f"admin_pick_{kind}_{page - 1}"))
        nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
        if page < total_pages:
            nav_row.append(InlineKeyboardButton(text="▶️", callback_data=f"admin_pick_{kind}_{page + 1}"))
        keyboard.append(nav_row)

    for text, callback_data in extra_buttons:
        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    if none_text:
        keyboard.append([InlineKeyboardButton(text=none_text, callback_data=f"{pick_prefix}0")])
    keyboard.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_fsm_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
