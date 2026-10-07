from typing import List, Dict, Any, Optional
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_brands_kb(brands: List[Any], page: int = 1, per_page: int = 8) -> InlineKeyboardMarkup:
    """Brendlar ro'yxati inline klaviaturasi (2 tadan qatorda)."""
    keyboard = []
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    current_page_brands = brands[start_idx:end_idx]

    row = []
    for b in current_page_brands:
        b_id = b["id"] if isinstance(b, dict) else b.id
        b_name = b["name"] if isinstance(b, dict) else b.name
        row.append(InlineKeyboardButton(text=f"🏷 {b_name}", callback_data=f"brand_{b_id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Pagination agar brendlar ko'p bo'lsa
    total_pages = max(1, (len(brands) + per_page - 1) // per_page)
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"brands_page_{page - 1}"))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"brands_page_{page + 1}"))
    if nav_row:
        keyboard.append(nav_row)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_categories_kb(
    categories: List[Any], brand_id: Optional[int] = None, page: int = 1, per_page: int = 8
) -> InlineKeyboardMarkup:
    """Toifalar ro'yxati inline klaviaturasi."""
    keyboard = []
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    current_page_cats = categories[start_idx:end_idx]

    for c in current_page_cats:
        c_id = c["id"] if isinstance(c, dict) else c.id
        c_name = c["name"] if isinstance(c, dict) else c.name
        cb_data = f"cat_{c_id}_{brand_id}" if brand_id else f"cat_{c_id}"
        keyboard.append([
            InlineKeyboardButton(text=f"📁 {c_name}", callback_data=cb_data)
        ])

    total_pages = max(1, (len(categories) + per_page - 1) // per_page)
    nav_row = []
    if page > 1:
        cb = f"cats_page_{brand_id}_{page - 1}" if brand_id else f"allcats_page_{page - 1}"
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=cb))
    if total_pages > 1:
        nav_row.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        cb = f"cats_page_{brand_id}_{page + 1}" if brand_id else f"allcats_page_{page + 1}"
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=cb))
    if nav_row:
        keyboard.append(nav_row)

    # Orqaga tugmasi
    if brand_id:
        keyboard.append([InlineKeyboardButton(text="⬅️ Brendlarga qaytish", callback_data="back_to_brands")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_products_list_kb(
    products: List[Any],
    page: int,
    total_pages: int,
    category_id: Optional[int] = None,
    brand_id: Optional[int] = None,
    search_query: Optional[str] = None,
) -> InlineKeyboardMarkup:
    """Tovarlar ro'yxati va pagination klaviaturasi."""
    keyboard = []

    for p in products:
        p_id = p["id"] if isinstance(p, dict) else p.id
        p_name = p["name"] if isinstance(p, dict) else p.name
        # Tugma uzunligini cheklash
        btn_text = p_name if len(p_name) <= 38 else p_name[:35] + "..."
        keyboard.append([
            InlineKeyboardButton(text=f"📦 {btn_text}", callback_data=f"prod_{p_id}")
        ])

    # Pagination qatori
    nav_row = []
    prefix = (
        f"prods_cat_{category_id}_brand_{brand_id}" if category_id and brand_id else
        f"prods_cat_{category_id}" if category_id else
        f"prods_brand_{brand_id}" if brand_id else
        f"prods_search"
    )

    if page > 1:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}_page_{page - 1}"))
    if total_pages > 0:
        nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data="noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}_page_{page + 1}"))

    if nav_row:
        keyboard.append(nav_row)

    # Orqaga qaytish tugmasi
    if category_id and brand_id:
        keyboard.append([InlineKeyboardButton(text="⬅️ Toifalarga qaytish", callback_data=f"back_brand_cats_{brand_id}")])
    elif category_id:
        keyboard.append([InlineKeyboardButton(text="⬅️ Toifalarga qaytish", callback_data="back_to_cats")])
    elif brand_id:
        keyboard.append([InlineKeyboardButton(text="⬅️ Brendlarga qaytish", callback_data="back_to_brands")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_product_detail_kb(
    product_id: int,
    quantity: int = 1,
    category_id: Optional[int] = None,
    brand_id: Optional[int] = None,
    page: int = 1,
) -> InlineKeyboardMarkup:
    """Bitta tovar kartochkasi klaviaturasi: - qty +, savatchaga qo'shish, orqaga."""
    keyboard = [
        [
            InlineKeyboardButton(text="➖", callback_data=f"qty_minus_{product_id}_{quantity}"),
            InlineKeyboardButton(text=f"{quantity} dona", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"qty_plus_{product_id}_{quantity}"),
        ],
        [
            InlineKeyboardButton(text="🛒 Savatchaga qo'shish", callback_data=f"add_cart_{product_id}_{quantity}"),
        ],
    ]

    # Qaytish tugmasi
    back_cb = (
        f"back_prods_cat_{category_id}_brand_{brand_id}_{page}" if category_id and brand_id else
        f"back_prods_cat_{category_id}_{page}" if category_id else
        f"back_prods_brand_{brand_id}_{page}" if brand_id else
        "back_to_search"
    )
    keyboard.append([InlineKeyboardButton(text="⬅️ Ro'yxatga qaytish", callback_data=back_cb)])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_cart_kb(cart_items: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """Savatcha klaviaturasi: har bir tovar boshqaruvi va buyurtma tasdiqlash."""
    keyboard = []

    for item in cart_items:
        cart_id = item["cart_id"]
        qty = item["quantity"]
        p_name = item["product_name"]
        short_name = p_name if len(p_name) <= 20 else p_name[:17] + "..."

        keyboard.append([
            InlineKeyboardButton(text=f"📦 {short_name}", callback_data="noop"),
        ])
        keyboard.append([
            InlineKeyboardButton(text="➖", callback_data=f"cart_minus_{cart_id}_{qty}"),
            InlineKeyboardButton(text=f"{qty} dona", callback_data="noop"),
            InlineKeyboardButton(text="➕", callback_data=f"cart_plus_{cart_id}_{qty}"),
            InlineKeyboardButton(text="❌ O'chirish", callback_data=f"cart_del_{cart_id}"),
        ])

    if cart_items:
        keyboard.append([
            InlineKeyboardButton(text="✅ Buyurtmani tasdiqlash", callback_data="checkout_order")
        ])
        keyboard.append([
            InlineKeyboardButton(text="🗑 Savatchani tozalash", callback_data="clear_cart")
        ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)
