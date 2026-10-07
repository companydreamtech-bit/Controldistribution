import os
import pytest
import pytest_asyncio
from controlpribor_bot.scraper import ControlPriborScraper, ScrapedProduct
from controlpribor_bot.database.db_manager import DatabaseManager

HTML_SNIPPET = """
<div class="product-item">
    <div class="product-item__image">
        <img src="data:image/png;base64,123" data-src="https://files.glotr.uz/products/item1.webp">
    </div>
    <div class="product-item__body">
        <a href="/proposal/fluke-303-123/" class="product-item__title">ПИРОМЕТР FLUKE 303</a>
        <div class="product-item__price">
            <span class="price">1 250 000 сум</span>
        </div>
    </div>
</div>
<div class="product-item">
    <div class="product-item__image">
        <img src="https://files.glotr.uz/products/item2.jpg">
    </div>
    <div class="product-item__body">
        <a href="/proposal/chint-rele-456/">Электромагнитное реле CHINT JZX-22F</a>
        <div class="product-item__price">
            <span class="price">По запросу</span>
        </div>
    </div>
</div>
"""

def test_parse_product_cards():
    scraper = ControlPriborScraper(base_url="https://controlpribor.uz")
    products = scraper.parse_products_html(HTML_SNIPPET, category_name="Pirometrlar")
    
    assert len(products) == 2
    p1 = products[0]
    assert p1.name == "ПИРОМЕТР FLUKE 303"
    assert "1 250 000" in p1.price
    assert p1.image_url == "https://files.glotr.uz/products/item1.webp"
    assert p1.product_url == "https://controlpribor.uz/proposal/fluke-303-123/"
    assert p1.category == "Pirometrlar"

    p2 = products[1]
    assert "CHINT" in p2.name
    assert p2.price == "Kelishilgan holda"
    assert p2.image_url == "https://files.glotr.uz/products/item2.jpg"

def test_identify_brand():
    scraper = ControlPriborScraper()
    assert scraper.extract_brand_name("ПИРОМЕТР ИНФРАКРАСНЫЙ FLUKE 568") == "Fluke"
    assert scraper.extract_brand_name("CHINT NXB-63 Avtomat") == "Chint"
    assert scraper.extract_brand_name("Akfix 705 universal yelim") == "Akfix"
    assert scraper.extract_brand_name("АКИП-4115/1 Осциллограф") == "АКИП"
    assert scraper.extract_brand_name("Mastech MY-64 Multimetr") == "Mastech"
    assert scraper.extract_brand_name("Noma'lum qurilma 123") == "Boshqa brendlar"

def test_export_to_excel(tmp_path):
    scraper = ControlPriborScraper()
    excel_file = tmp_path / "catalog_test.xlsx"
    products = [
        ScrapedProduct(
            name="Fluke 303",
            price="1 000 000 so'm",
            category="O'lchov asboblari",
            brand="Fluke",
            image_url="https://example.com/1.jpg",
            product_url="https://controlpribor.uz/1"
        )
    ]
    scraper.export_to_excel(products, filename=str(excel_file))
    assert os.path.exists(excel_file)
    assert os.path.getsize(excel_file) > 1000

@pytest.mark.asyncio
async def test_save_to_database(tmp_path):
    db_file = tmp_path / "test_scraper_db.db"
    db = DatabaseManager(f"sqlite+aiosqlite:///{db_file}")
    await db.init_db()

    scraper = ControlPriborScraper()
    products = [
        ScrapedProduct(
            name="Fluke 303 Klesh",
            price="1 000 000 so'm",
            category="Kleshlar",
            brand="Fluke",
            image_url="https://example.com/303.jpg",
            product_url="https://controlpribor.uz/p1"
        ),
        ScrapedProduct(
            name="Akfix 705 Yelim",
            price="Kelishilgan holda",
            category="Yelimlar",
            brand="Akfix",
            image_url=None,
            product_url="https://controlpribor.uz/p2"
        ),
    ]

    saved_count = await scraper.save_to_db(products, db)
    assert saved_count == 2

    # Check products in db
    brands = await db.get_brands()
    brand_names = [b.name for b in brands]
    assert "Fluke" in brand_names
    assert "Akfix" in brand_names

    res, total = await db.search_products("Fluke")
    assert total == 1
    assert res[0].name == "Fluke 303 Klesh"

    await db.close()
