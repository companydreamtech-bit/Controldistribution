from types import SimpleNamespace

import pytest
import pytest_asyncio

from controlpribor_bot.database.db_manager import DatabaseManager

PREFIX = "https://t.me/asfdistribution/"


@pytest_asyncio.fixture
async def db(tmp_path):
    manager = DatabaseManager(f"sqlite+aiosqlite:///{tmp_path / 'cleanup.db'}")
    await manager.init_db()
    yield manager
    await manager.close()


async def seed(db: DatabaseManager):
    fluke = await db.add_brand("Fluke", "fluke")
    chint = await db.add_brand("CHINT", "chint")
    cat = await db.find_category("Instrumentlar")
    old_tool = await db.add_product("ПИРОМЕТР FLUKE 568", price="1 865 000 so'm", brand_id=fluke.id, category_id=cat.id)
    old_chint = await db.add_product("Old CHINT relay", brand_id=chint.id)
    channel = await db.add_product("SMASH степлер", price="4.5$", category_id=cat.id, product_url=PREFIX + "319")
    channel_chint = await db.add_product("CHINT NXB-63", brand_id=chint.id, product_url=PREFIX + "234")
    return SimpleNamespace(fluke=fluke, chint=chint, cat=cat, old_tool=old_tool, old_chint=old_chint,
                           channel=channel, channel_chint=channel_chint)


@pytest.mark.asyncio
async def test_delete_products_not_from_channel(db: DatabaseManager):
    s = await seed(db)
    user, _ = await db.get_or_create_user(1, "Mijoz", "+998901234567")
    await db.add_to_cart(user.id, s.old_tool.id)
    await db.add_to_cart(user.id, s.channel.id)
    await db.create_order(user.id, "1 865 000 so'm", [{
        "product_id": s.old_tool.id, "product_name": s.old_tool.name, "quantity": 1, "price": s.old_tool.price,
    }])

    assert await db.count_products_not_from(PREFIX) == 2
    deleted, removed_brands = await db.delete_products_not_from(PREFIX)

    assert sorted(deleted) == sorted([s.old_tool.id, s.old_chint.id])
    assert removed_brands == 1  # Fluke bo'sh qoldi, CHINT'da kanal tovari bor
    assert await db.get_brand_by_id(s.fluke.id) is None
    assert await db.get_brand_by_id(s.chint.id) is not None
    assert await db.get_product_by_id(s.channel.id) is not None
    assert await db.find_category("Instrumentlar") is not None
    assert [i["product_name"] for i in await db.get_cart_items(user.id)] == ["SMASH степлер"]
    assert (await db.get_stats())["orders"] == 1  # buyurtmalar tarixi saqlanadi

    assert await db.count_products_not_from(PREFIX) == 0
    assert await db.delete_products_not_from(PREFIX) == ([], 0)


@pytest.mark.asyncio
async def test_brand_used_by_category_is_kept(db: DatabaseManager):
    brand = await db.add_brand("Testo", "testo")
    await db.add_category("Testo termometrlari", brand_id=brand.id)
    await db.add_product("Testo 830", brand_id=brand.id)

    _, removed_brands = await db.delete_products_not_from(PREFIX)

    assert removed_brands == 0
    assert await db.get_brand_by_id(brand.id) is not None
