import pytest
from controlpribor_bot.keyboards.default_kb import get_main_menu_kb, get_contact_kb
from controlpribor_bot.keyboards.inline_kb import (
    get_brands_kb,
    get_categories_kb,
    get_products_list_kb,
    get_product_detail_kb,
    get_cart_kb,
)
from controlpribor_bot.utils.pagination import Paginator

def test_main_menu_and_contact_kb():
    menu = get_main_menu_kb()
    assert len(menu.keyboard) >= 3
    buttons_text = [btn.text for row in menu.keyboard for btn in row]
    assert "📦 Tovarlar" in buttons_text
    assert "🏷 Brendlar" not in buttons_text and "📁 Barcha kategoriyalar" not in buttons_text
    assert "🔍 Tovar qidirish" in buttons_text
    assert "🛒 Savatcha" in buttons_text
    assert "📞 Bog'lanish / Menejer" in buttons_text

    contact_kb = get_contact_kb()
    assert contact_kb.keyboard[0][0].request_contact is True

def test_paginator():
    items = list(range(1, 26))  # 25 items
    paginator = Paginator(items, per_page=6)
    assert paginator.total_pages == 5
    page_1 = paginator.get_page(1)
    assert len(page_1) == 6
    assert page_1[0] == 1
    page_5 = paginator.get_page(5)
    assert len(page_5) == 1
    assert page_5[0] == 25

def test_inline_brands_and_categories():
    brands = [{"id": 1, "name": "Fluke"}, {"id": 2, "name": "Chint"}]
    kb = get_brands_kb(brands)
    assert len(kb.inline_keyboard) >= 1
    assert kb.inline_keyboard[0][0].callback_data == "brand_1"

    categories = [{"id": 10, "name": "Multimetrlar"}]
    cat_kb_brand = get_categories_kb(categories, brand_id=1)
    assert cat_kb_brand.inline_keyboard[0][0].callback_data == "cat_10_1"
    cat_kb_all = get_categories_kb(categories, brand_id=None)
    assert cat_kb_all.inline_keyboard[0][0].callback_data == "cat_10"

def test_inline_product_detail_and_cart():
    prod_kb = get_product_detail_kb(product_id=5, quantity=2, category_id=10, page=1)
    cb_data = [btn.callback_data for row in prod_kb.inline_keyboard for btn in row]
    assert "qty_minus_5_2" in cb_data
    assert "qty_plus_5_2" in cb_data
    assert "add_cart_5_2" in cb_data

    cart_items = [
        {"cart_id": 1, "product_id": 5, "product_name": "Fluke 303", "quantity": 2, "price": "1 000 000 so'm"}
    ]
    cart_kb = get_cart_kb(cart_items)
    cart_cb = [btn.callback_data for row in cart_kb.inline_keyboard for btn in row]
    assert "cart_minus_1_2" in cart_cb
    assert "cart_plus_1_2" in cart_cb
    assert "cart_del_1" in cart_cb
    assert "checkout_order" in cart_cb
    assert "clear_cart" in cart_cb


def test_brand_and_category_icons():
    from types import SimpleNamespace
    from controlpribor_bot.keyboards.icons import brand_icon, category_icon
    from controlpribor_bot.keyboards.inline_kb import get_brands_kb, get_categories_kb

    assert brand_icon("BAUMANN ELECTRIC") == "💡"
    assert brand_icon("Noma'lum brend") == "🏷"
    assert category_icon("Instrumentlar") == "🛠"
    assert category_icon("AKFIX") == "🧴"  # brend nomli kategoriya
    assert category_icon("Yangi kategoriya") == "📁"

    brands_kb = get_brands_kb([SimpleNamespace(id=1, name="CHINT")])
    assert brands_kb.inline_keyboard[0][0].text == "⚡ CHINT"
    cats_kb = get_categories_kb([SimpleNamespace(id=2, name="Kabellar")])
    assert cats_kb.inline_keyboard[0][0].text == "🔗 Kabellar"
