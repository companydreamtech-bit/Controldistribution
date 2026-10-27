import pytest
import os
from controlpribor_bot.config import Config
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.keyboards.default_kb import get_main_menu_kb
from controlpribor_bot.keyboards.admin_kb import (
    get_admin_main_kb,
    get_admin_products_kb,
    get_admin_brands_kb,
    get_admin_categories_kb,
    get_product_admin_actions_kb,
)
from controlpribor_bot.bot import setup_dispatcher


def test_main_menu_kb_with_admin():
    kb_user = get_main_menu_kb(is_admin=False)
    all_buttons_user = [btn.text for row in kb_user.keyboard for btn in row]
    assert "⚙️ Admin panel" not in all_buttons_user

    kb_admin = get_main_menu_kb(is_admin=True)
    all_buttons_admin = [btn.text for row in kb_admin.keyboard for btn in row]
    assert "⚙️ Admin panel" in all_buttons_admin


def test_admin_keyboards():
    main_kb = get_admin_main_kb()
    assert len(main_kb.inline_keyboard) == 3

    prod_kb = get_admin_products_kb()
    assert any(btn.callback_data == "admin_prod_add" for row in prod_kb.inline_keyboard for btn in row)

    brand_kb = get_admin_brands_kb()
    assert any(btn.callback_data == "admin_brand_add" for row in brand_kb.inline_keyboard for btn in row)

    cat_kb = get_admin_categories_kb()
    assert any(btn.callback_data == "admin_cat_add" for row in cat_kb.inline_keyboard for btn in row)

    actions_kb = get_product_admin_actions_kb(product_id=42)
    assert any("42" in btn.callback_data for row in actions_kb.inline_keyboard for btn in row)


@pytest.mark.asyncio
async def test_admin_crud_db_operations(tmp_path):
    db_file = tmp_path / "test_admin.db"
    db = DatabaseManager(f"sqlite+aiosqlite:///{db_file}")
    await db.init_db()

    # 1. Add and delete Brand
    brand = await db.add_brand(name="Test Brand", slug="test-brand")
    assert brand.id is not None
    brand_del_res = await db.delete_brand(brand.id)
    assert brand_del_res is True
    assert await db.get_brand_by_id(brand.id) is None

    # 2. Add and delete Category
    cat = await db.add_category(name="Test Category")
    assert cat.id is not None
    cat_del_res = await db.delete_category(cat.id)
    assert cat_del_res is True
    assert await db.get_category_by_id(cat.id) is None

    # 3. Add, update, and delete Product
    prod = await db.add_product(
        name="Test Tool 100",
        price="500 000 so'm",
        description="Original description",
    )
    assert prod.id is not None

    # Update fields
    updated_prod = await db.update_product_fields(
        prod.id,
        price="600 000 so'm",
        name="Test Tool 200",
        description="Updated description",
    )
    assert updated_prod is not None
    assert updated_prod.price == "600 000 so'm"
    assert updated_prod.name == "Test Tool 200"
    assert updated_prod.description == "Updated description"

    # Get stats
    stats = await db.get_stats()
    assert "users" in stats
    assert "products" in stats
    assert stats["products"] >= 1

    # Delete product
    prod_del_res = await db.delete_product(prod.id)
    assert prod_del_res is True
    assert await db.get_product_by_id(prod.id) is None

    await db.close()


def test_admin_router_in_dispatcher(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST_TOKEN")
    config = Config.load()
    db = DatabaseManager("sqlite+aiosqlite:///test.db")
    dp = setup_dispatcher(db=db, config=config)
    router_names = [r.name for r in dp.sub_routers]
    assert "admin_router" in router_names
