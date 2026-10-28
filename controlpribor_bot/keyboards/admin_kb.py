from typing import List, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from controlpribor_bot.database.models import Brand, Category, Product
from controlpribor_bot.keyboards.icons import brand_icon, category_icon


def get_admin_main_kb() -> InlineKeyboardMarkup:
    """Admin asosiy boshqaruv menyusi."""
    keyboard = [
        [
            InlineKeyboardButton(text="📦 Mahsulotlar", callback_data="admin_products"),
            InlineKeyboardButton(text="🏷 Brendlar", callback_data="admin_brands"),
        ],
        [
            InlineKeyboardButton(text="📁 Kategoriyalar", callback_data="admin_categories"),
            InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
        ],
        [
            InlineKeyboardButton(text="📥 Kanaldan import (@asfdistribution)", callback_data="admin_import_channel"),
        ],
        [
            InlineKeyboardButton(text="🧹 Kanaldan kelmagan eski tovarlarni o'chirish", callback_data="admin_cleanup_old"),
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
        [InlineKeyboardButton(text="⬅️ Admin menyusiga qaytish", callback_data="admin_back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_brands_kb() -> InlineKeyboardMarkup:
    """Brendlar bo'limi klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton(text="➕ Yangi brend qo'shish", callback_data="admin_brand_add")],
        [InlineKeyboardButton(text="📋 Barcha brendlar ro'yxati", callback_data="admin_brand_list_1")],
        [InlineKeyboardButton(text="⬅️ Admin menyusiga qaytish", callback_data="admin_back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_admin_categories_kb() -> InlineKeyboardMarkup:
    """Kategoriyalar bo'limi klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton(text="➕ Yangi kategoriya qo'shish", callback_data="admin_cat_add")],
        [InlineKeyboardButton(text="📋 Barcha kategoriyalar ro'yxati", callback_data="admin_cat_list_1")],
        [InlineKeyboardButton(text="⬅️ Admin menyusiga qaytish", callback_data="admin_back_main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_brands_page_kb(brands: List[Brand], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Brendlar ro'yxati va o'chirish tugmalari."""
    keyboard = []
    for b in brands:
        keyboard.append([
            InlineKeyboardButton(text=f"{brand_icon(b.name)} {b.name}", callback_data=f"admin_brand_view_{b.id}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_brand_del_{b.id}"),
        ])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"admin_brand_list_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{max(1, total_pages)}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"admin_brand_list_{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_brands")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_categories_page_kb(categories: List[Category], page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Kategoriyalar ro'yxati va o'chirish tugmalari."""
    keyboard = []
    for c in categories:
        brand_name = f" ({c.brand.name})" if c.brand else ""
        keyboard.append([
            InlineKeyboardButton(text=f"{category_icon(c.name)} {c.name[:25]}{brand_name}", callback_data=f"admin_cat_view_{c.id}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_cat_del_{c.id}"),
        ])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Oldingi", callback_data=f"admin_cat_list_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{max(1, total_pages)}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Keyingi ▶️", callback_data=f"admin_cat_list_{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    keyboard.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="admin_categories")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_product_admin_actions_kb(product_id: int) -> InlineKeyboardMarkup:
    """Tanlangan mahsulotni boshqarish klaviaturasi."""
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
            InlineKeyboardButton(text="🏷 Brendni o'zgartirish", callback_data=f"admin_prod_edit_brand_{product_id}"),
            InlineKeyboardButton(text="📁 Kategoriyani o'zgartirish", callback_data=f"admin_prod_edit_cat_{product_id}"),
        ],
        [
            InlineKeyboardButton(text="🗑 Mahsulotni o'chirish", callback_data=f"admin_prod_del_{product_id}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Mahsulotlar bo'limiga", callback_data="admin_products"),
        ],
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


def get_brand_admin_card_kb(brand_id: int) -> InlineKeyboardMarkup:
    """Tanlangan brendni boshqarish klaviaturasi."""
    keyboard = [
        [InlineKeyboardButton(text="✏️ Nomini o'zgartirish", callback_data=f"admin_brand_rename_{brand_id}")],
        [InlineKeyboardButton(text="🗑 Brendni o'chirish", callback_data=f"admin_brand_del_{brand_id}")],
        [InlineKeyboardButton(text="⬅️ Brendlar ro'yxatiga", callback_data="admin_brand_list_1")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_category_admin_card_kb(category_id: int) -> InlineKeyboardMarkup:
    """Tanlangan kategoriyani boshqarish klaviaturasi."""
    keyboard = [
        [
            InlineKeyboardButton(text="✏️ Nomini o'zgartirish", callback_data=f"admin_cat_rename_{category_id}"),
            InlineKeyboardButton(text="🏷 Brendini o'zgartirish", callback_data=f"admin_cat_chbrand_{category_id}"),
        ],
        [InlineKeyboardButton(text="🗑 Kategoriyani o'chirish", callback_data=f"admin_cat_del_{category_id}")],
        [InlineKeyboardButton(text="⬅️ Kategoriyalar ro'yxatiga", callback_data="admin_cat_list_1")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


PICKER_PER_PAGE = 10


def get_picker_kb(
    items: List, kind: str, pick_prefix: str, none_text: str, page: int = 1
) -> InlineKeyboardMarkup:
    """Brend yoki kategoriyani sahifalab tanlash klaviaturasi.

    Tanlov tugmasi: f"{pick_prefix}{id}" ("0" — tanlanmagan), sahifa tugmasi: f"admin_pick_{kind}_{page}".
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

    keyboard.append([InlineKeyboardButton(text=none_text, callback_data=f"{pick_prefix}0")])
    keyboard.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_fsm_cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
