import os
import pytest
import pytest_asyncio
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.database.models import User, Brand, Category, Product, Cart, Order, OrderItem

TEST_DB = "test_catalog.db"

@pytest_asyncio.fixture
async def db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    manager = DatabaseManager(db_url=f"sqlite+aiosqlite:///{TEST_DB}")
    await manager.init_db()
    yield manager
    await manager.close()
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)

@pytest.mark.asyncio
async def test_user_creation_and_retrieval(db: DatabaseManager):
    user, created = await db.get_or_create_user(
        telegram_id=12345678,
        full_name="Alisher Karimov",
        phone_number="+998901234567"
    )
    assert created is True
    assert user.full_name == "Alisher Karimov"
    assert user.telegram_id == 12345678

    # Second call should not recreate
    user2, created2 = await db.get_or_create_user(
        telegram_id=12345678,
        full_name="Alisher Karimov",
        phone_number="+998901234567"
    )
    assert created2 is False
    assert user2.id == user.id

@pytest.mark.asyncio
async def test_brands_and_categories(db: DatabaseManager):
    brand = await db.add_brand(name="Fluke", slug="fluke")
    assert brand.id is not None

    category = await db.add_category(name="Tokoviy kleshlar", brand_id=brand.id)
    assert category.id is not None
    assert category.brand_id == brand.id

    brands = await db.get_brands()
    assert len(brands) == 1
    assert brands[0].name == "Fluke"

    categories = await db.get_categories_by_brand(brand.id)
    assert len(categories) == 1
    assert categories[0].name == "Tokoviy kleshlar"

@pytest.mark.asyncio
async def test_products_crud_and_search(db: DatabaseManager):
    brand = await db.add_brand(name="Fluke", slug="fluke")
    cat = await db.add_category(name="Kleshlar", brand_id=brand.id)
    
    p1 = await db.add_product(
        name="Fluke 303 Tokoviy klesh",
        price="1 000 000 so'm",
        brand_id=brand.id,
        category_id=cat.id,
        image_url="https://example.com/303.jpg",
        description="Tok o'lchov asbobi"
    )
    p2 = await db.add_product(
        name="Akfix 705 Yelim",
        price="Kelishilgan holda",
        brand_id=None,
        category_id=cat.id,
        image_url=None,
        description="Tezkor yelim"
    )

    # Search for "303"
    results, total = await db.search_products(query="303", page=1, limit=10)
    assert total == 1
    assert results[0].name == "Fluke 303 Tokoviy klesh"

    # Search for "klesh" (case insensitive)
    results2, total2 = await db.search_products(query="klesh", page=1, limit=10)
    assert total2 == 1

@pytest.mark.asyncio
async def test_cart_and_order_flow(db: DatabaseManager):
    user, _ = await db.get_or_create_user(999, "Test User", "+998900000000")
    prod = await db.add_product(
        name="Mastech MY-64 Multimetr",
        price="350 000 so'm",
        brand_id=None,
        category_id=None
    )

    # Add to cart
    cart_item = await db.add_to_cart(user_id=user.id, product_id=prod.id, quantity=2)
    assert cart_item.quantity == 2

    # Add same product again -> quantity should increment
    await db.add_to_cart(user_id=user.id, product_id=prod.id, quantity=1)
    items = await db.get_cart_items(user_id=user.id)
    assert len(items) == 1
    assert items[0]["quantity"] == 3

    # Update quantity
    await db.update_cart_quantity(cart_id=items[0]["cart_id"], quantity=4)
    items_after = await db.get_cart_items(user_id=user.id)
    assert items_after[0]["quantity"] == 4

    # Create order
    order = await db.create_order(
        user_id=user.id,
        total_price="1 400 000 so'm",
        items=items_after
    )
    assert order.id is not None
    assert order.user_id == user.id

    # Cart should be clear after order or explicitly
    await db.clear_cart(user_id=user.id)
    empty_items = await db.get_cart_items(user_id=user.id)
    assert len(empty_items) == 0
