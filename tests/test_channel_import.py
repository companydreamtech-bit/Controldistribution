from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from aiogram.types import FSInputFile

from controlpribor_bot.channel_import import (
    ChannelPost,
    detect_category,
    extract_price,
    import_channel,
    parse_channel_page,
    parse_post,
)
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.handlers.cart import format_cart_message, parse_price
from controlpribor_bot.handlers.catalog import resolve_photo

CONTACTS = "\n\n📞 50 515 51 11\n📞 99 901 59 11\n📲 @S_77777_S\n📲 @controldistribution"


def post(text: str, post_id: int = 1, image: str = "https://cdn.example/img.jpg") -> ChannelPost:
    return ChannelPost(post_id=post_id, text=text, image_src=image)


# --- Postlarni tahlil qilish (kanaldagi haqiqiy post namunalari) ---
def test_simple_tool_post():
    p = parse_post(post("XITE метр Рулетка:\n\n3м - 0.87$\n5м - 1.24$\n10м - 1.95$" + CONTACTS, 334))
    assert p.name == "XITE метр Рулетка"
    assert p.brand == "Xite"
    assert p.category == "Instrumentlar"
    assert p.price == "0.87$ – 1.95$"
    assert "📞" not in p.description and "5м - 1.24$" in p.description
    assert p.post_url == "https://t.me/asfdistribution/334"


def test_brand_header_with_subtitle_and_sum_prices():
    text = (
        "⚡️ PROCAB — PROFESSIONAL CABLE\n\nМногожильные кабели ПУГНП: \n\n"
        "ПУГНП 2*0.50 - 2520 сум\nПУГНП 2*1.5    - 6210 сум\nПУГНП 3*2.5    - 15840 сум" + CONTACTS
    )
    p = parse_post(post(text, 245))
    assert p.name == "PROCAB — Многожильные кабели ПУГНП"
    assert p.brand == "Procab"
    assert p.category == "PROCAB"
    assert p.price == "2 520 so'm – 15 840 so'm"


def test_dash_prices_without_currency_are_usd():
    text = (
        "⚡️ NILSON TOURAN — ZAMONAVIY VA ISHONCHLI ELEKTROFURNITURA\n\n"
        "TOURAN Выкл. 1-кл. Nilson — 1,35\nTOURAN Розетка Nilson — 1,35\nTOURAN Рамка 2' Nilson — 0,80" + CONTACTS
    )
    p = parse_post(post(text, 238))
    assert p.brand == "Nilson"
    assert p.category == "NILSON"
    assert p.price == "0.8$ – 1.35$"


def test_model_code_is_not_price():
    text = "⚡️Контактор NC1-9511\n\n❗CHINT\n\n📍 Хизмат ҳудудлари:\n🇺🇿 Ўзбекистон барча вилоятлари"
    p = parse_post(post(text, 141))
    assert p.name == "Контактор NC1-9511 — Chint"
    assert p.price == "Kelishilgan holda"
    assert p.category == "CHINT"
    assert p.description == "❗CHINT"  # xizmat shartlari tavsifga kirmaydi


def test_brand_only_header_uses_common_variant_prefix():
    text = (
        "CHINT ❗❗❗\n\nABP NDS2-125/3P 100A — 85$\nABP NDS2-160/3P 160A — 130$\n"
        "ABP NDS2-1000/3P 800A — 1 000$" + CONTACTS
    )
    p = parse_post(post(text, 250))
    assert p.name == "CHINT — ABP NDS2"
    assert p.price == "85$ – 1000$"


def test_slogan_first_line_takes_model_from_next_line():
    text = "⚡ Kuchlanishdagi o‘zgarishlardan himoyalaning!\nCHINT TM-1 — qurilmalaringiz uchun barqaror kuchlanish."
    p = parse_post(post(text, 169))
    assert p.name == "CHINT TM-1"
    assert p.category == "CHINT"


@pytest.mark.parametrize("text", [
    "AKSIYA\n20.07.2026 gacha amal qiladi!",
    "Nega aynan 915N?\n✔️ UV va namlikka chidamli — tashqi jabhada uzoq xizmat qiladi",
    "ASF Distribution - rasmiy distribyutor pinned a photo",
    "",
    "Bugundan START berdik!",
])
def test_non_product_posts_are_skipped(text):
    assert parse_post(post(text)) is None


def test_unknown_product_is_flagged_for_review():
    p = parse_post(post('20W"  - 0.90$\n30W" - 1.20$' + CONTACTS, 9306))
    assert p.needs_review
    assert p.category == "Boshqa tovarlar"


@pytest.mark.parametrize("name, expected", [
    ("NURA ELECTRIC — Стабилизатор релейный", "Stabilizatorlar"),
    ("NURA ELECTRIC NP03 — PODROZETNIK", "Montaj aksessuarlari"),
    ("BAUMANN ELECTRIC — Светильник 3W на розетку", "Yoritish"),
    ("Розетка с защит. Шторкой", "Rozetka va o'chirgichlar"),  # "защит" — "щит" emas
    ("Щит металл ЩМП 300*250*110мм IP65", "Metall shitlar"),
    ("PERFORATSIYALANGAN KABEL KANALI (PERFOKORP)", "gofra va korp"),
    ("CHINT NXB-63 — AVTOMATIK O'CHIRGICH", "Avtomatika va himoya"),
    ("Монтажная пена 872", "Germetik va qurilish kimyosi"),
])
def test_detect_category(name, expected):
    assert detect_category(name, [name], None) == expected


def test_extract_price_formats():
    assert extract_price(["250×250×110 - 0,3 mm - $2,1", "350×250×110 - 0,3 mm - $2,4"]) == "2.1$ – 2.4$"
    assert extract_price(["💵 13.000 сум"]) == "13 000 so'm"
    assert extract_price(["Малярный нож:", "- 0.17$"]) == "0.17$"
    assert extract_price(["Hech qanday narx yo'q"]) == "Kelishilgan holda"


# --- Kanal sahifasi ---
PAGE_HTML = """
<div class="tgme_widget_message" data-post="asfdistribution/10">
  <a class="tgme_widget_message_photo_wrap" style="width:800px;background-image:url('https://cdn.example/10.jpg')"></a>
  <div class="tgme_widget_message_text">SMASH степлер:<br/><br/>- 4.5$<br/><br/>📞 50 515 51 11</div>
</div>
<div class="tgme_widget_message" data-post="asfdistribution/11">
  <i class="tgme_widget_message_video_thumb" style="background-image:url('https://cdn.example/11.jpg')"></i>
  <div class="tgme_widget_message_text">💡 LED лампочка 15W<br/><br/>❗ TESS</div>
</div>
<div class="tgme_widget_message" data-post="asfdistribution/12">
  <div class="tgme_widget_message_text">AKSIYA<br/>20.07.2026 gacha!</div>
</div>
"""


def test_parse_channel_page():
    posts = parse_channel_page(PAGE_HTML)
    assert [p.post_id for p in posts] == [10, 11, 12]
    assert posts[0].text.startswith("SMASH степлер:\n\n- 4.5$")
    assert posts[0].image_src == "https://cdn.example/10.jpg"
    assert posts[1].image_src == "https://cdn.example/11.jpg"  # video posti — muqova rasmi
    assert posts[2].image_src is None


# --- To'liq import (soxta HTTP) ---
@pytest_asyncio.fixture
async def db(tmp_path):
    manager = DatabaseManager(f"sqlite+aiosqlite:///{tmp_path / 'import.db'}")
    await manager.init_db()
    yield manager
    await manager.close()


def make_client(page_html: str, requests: list) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if request.url.host == "t.me":
            # Birinchi sahifa postlarni beradi, eskiroq sahifa bo'sh
            body = page_html if "before" not in request.url.params else "<html></html>"
            return httpx.Response(200, text=body)
        return httpx.Response(200, content=b"\xff\xd8fake-jpeg")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_import_channel_creates_and_updates(db: DatabaseManager, tmp_path: Path):
    media = tmp_path / "media"
    requests = []
    async with make_client(PAGE_HTML, requests) as client:
        result = await import_channel(db, media, client=client)

    assert (result.created, result.updated, result.skipped, result.images) == (2, 0, 1, 2)
    stapler = await db.get_product_by_url("https://t.me/asfdistribution/10")
    stapler = await db.get_product_by_id(stapler.id)
    assert stapler.name == "SMASH степлер"
    assert stapler.price == "4.5$"
    assert stapler.brand.name == "Smash"
    assert stapler.category.name == "Instrumentlar"
    assert stapler.image_url == "media/asf_10.jpg"
    assert (media / "asf_10.jpg").read_bytes().startswith(b"\xff\xd8")

    lamp = await db.get_product_by_url("https://t.me/asfdistribution/11")
    lamp = await db.get_product_by_id(lamp.id)
    assert lamp.name == "LED лампочка 15W — Tess"
    assert lamp.category.name == "TESS"

    # Admin nomni o'zgartiradi, kanalda narx o'zgaradi -> qayta import nomni saqlab, narxni yangilaydi
    await db.update_product_fields(stapler.id, name="Stepler SMASH (admin)")
    new_page = PAGE_HTML.replace("- 4.5$", "- 5$")
    requests.clear()
    async with make_client(new_page, requests) as client:
        again = await import_channel(db, media, client=client)

    assert (again.created, again.updated, again.images) == (0, 2, 0)
    assert not any("cdn.example" in url for url in requests)  # rasm qayta yuklanmaydi
    stapler = await db.get_product_by_id(stapler.id)
    assert stapler.name == "Stepler SMASH (admin)"
    assert stapler.price == "5$"
    assert (await db.get_stats())["products"] == 2


@pytest.mark.asyncio
async def test_import_dry_run_writes_nothing(db: DatabaseManager, tmp_path: Path):
    async with make_client(PAGE_HTML, []) as client:
        result = await import_channel(db, tmp_path / "media", client=client, dry_run=True)
    assert len(result.products) == 2
    assert (await db.get_stats())["products"] == 0
    assert not (tmp_path / "media").exists()


@pytest.mark.asyncio
async def test_duplicate_names_get_variant_suffix(db: DatabaseManager, tmp_path: Path):
    page = """
    <div class="tgme_widget_message" data-post="c/1"><div class="tgme_widget_message_text">Заклёпка аппарат:<br/>ST-1086 - 8$</div></div>
    <div class="tgme_widget_message" data-post="c/2"><div class="tgme_widget_message_text">Заклёпка аппарат:<br/>ST-1010 - 2.50$</div></div>
    """
    async with make_client(page, []) as client:
        result = await import_channel(db, tmp_path / "media", client=client)
    assert [p.name for p in result.products] == ["Заклёпка аппарат", "Заклёпка аппарат ST-1010"]


# --- Savatcha va rasm ---
def test_cart_parse_price():
    assert parse_price("1 500 000 so'm") == (1500000.0, "so'm")
    assert parse_price("0.87$") == (0.87, "$")
    assert parse_price("1 000$") == (1000.0, "$")
    assert parse_price("0.4$ – 1.1$") == (None, "")
    assert parse_price("2 520 so'm – 26 000 so'm") == (None, "")
    assert parse_price("Kelishilgan holda") == (None, "")


def test_cart_totals_by_currency():
    items = [
        {"product_name": "A", "price": "10 000 so'm", "quantity": 2},
        {"product_name": "B", "price": "0.87$", "quantity": 3},
        {"product_name": "C", "price": "0.4$ – 1.1$", "quantity": 1},
    ]
    text, total = format_cart_message(items)
    assert total == "20 000 so'm + 2.61$ (+ kelishilgan tovarlar)"
    assert "3 dona × 0.87$ = <b>2.61$</b>" in text


def test_resolve_photo(tmp_path: Path):
    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "asf_1.jpg").write_bytes(b"x")
    db_path = str(tmp_path / "database.db")

    local = resolve_photo("media/asf_1.jpg", db_path)
    assert isinstance(local, FSInputFile)
    assert resolve_photo("media/missing.jpg", db_path) is None
    assert resolve_photo("https://example.com/a.jpg", db_path) == "https://example.com/a.jpg"
    assert resolve_photo("AgACAgIAAxkBAAI", db_path) == "AgACAgIAAxkBAAI"
    assert resolve_photo(None, db_path) is None


@pytest.mark.asyncio
async def test_post_overrides_fix_already_imported_products(db: DatabaseManager, tmp_path: Path):
    # Avvalgi import #306 ni noaniq nom bilan yozgan
    old = await db.add_product(
        name='Tovar — 20W" / 30W"', price="0.9$ – 2.3$",
        product_url="https://t.me/asfdistribution/306",
    )
    page = """
    <div class="tgme_widget_message" data-post="asfdistribution/306">
      <div class="tgme_widget_message_text">20W"  - 0.90$<br/>30W" - 1.20$<br/>50W" - 2.30$</div>
    </div>
    <div class="tgme_widget_message" data-post="asfdistribution/330">
      <div class="tgme_widget_message_text">- для электролобзика<br/><br/>- 0.53$</div>
    </div>
    """
    async with make_client(page, []) as client:
        result = await import_channel(db, tmp_path / "media", client=client)

    assert result.needs_review == []
    assert (result.created, result.updated) == (1, 1)

    lamp = await db.get_product_by_id(old.id)
    assert lamp.name == "VOLT LED lampochka (20W–50W)"
    assert lamp.brand.name == "Volt"
    assert lamp.category.name == "Boshqa tovarlar"  # Volt brendi 16 tadan tashqarida
    assert lamp.price == "0.9$ – 2.3$"

    blades = await db.get_product_by_url("https://t.me/asfdistribution/330")
    blades = await db.get_product_by_id(blades.id)
    assert blades.name == "Пилки для электролобзика"
    assert blades.category.name == "Instrumentlar"


@pytest.mark.asyncio
async def test_reimport_keeps_admin_price_when_post_has_none(db: DatabaseManager, tmp_path: Path):
    page = """
    <div class="tgme_widget_message" data-post="asfdistribution/11">
      <div class="tgme_widget_message_text">💡 LED лампочка 15W<br/><br/>❗ TESS</div>
    </div>
    """
    async with make_client(page, []) as client:
        await import_channel(db, tmp_path / "media", client=client)
    lamp = await db.get_product_by_url("https://t.me/asfdistribution/11")
    assert lamp.price == "Kelishilgan holda"

    await db.update_product_fields(lamp.id, price="12 000 so'm")
    async with make_client(page, []) as client:
        await import_channel(db, tmp_path / "media", client=client)

    assert (await db.get_product_by_id(lamp.id)).price == "12 000 so'm"


# --- Botdagi 16 ta kategoriya ---
@pytest.mark.parametrize("kind, brand, expected", [
    ("Metall shitlar", "Profmet", "Metall shitlar"),
    ("Montaj aksessuarlari", "Profmet", "Metall shitlar"),
    ("gofra va korp", None, "gofra va korp"),
    ("Yoritish", "Baumann Electric", "BAUMANN ELECTRIC"),
    ("Instrumentlar", "Baumann Electric", "BAUMANN ELECTRIC"),
    ("Instrumentlar", "Smash", "Instrumentlar"),
    ("Instrumentlar", None, "Instrumentlar"),
    ("Kabellar", "Uzkabel", "UZKABEL"),
    ("Yoritish", "Redray", "Boshqa tovarlar"),
    ("Stabilizatorlar", "Balance", "Boshqa tovarlar"),
])
def test_shop_category(kind, brand, expected):
    from controlpribor_bot.channel_import import shop_category
    assert shop_category(kind, brand) == expected


@pytest.mark.asyncio
async def test_reimport_moves_products_out_of_legacy_categories(db: DatabaseManager, tmp_path: Path):
    # Oldingi versiya tovarni "Yoritish" tur kategoriyasiga joylagan
    legacy = await db.add_category("Yoritish")
    lamp = await db.add_product("LED лампочка 15W — Tess", category_id=legacy.id,
                                product_url="https://t.me/asfdistribution/11")
    # Admin qo'lda 16 tadan biriga qo'ygan tovar o'z joyida qolishi kerak
    instruments = await db.find_category("Instrumentlar")
    stapler = await db.add_product("SMASH степлер", category_id=instruments.id,
                                   product_url="https://t.me/asfdistribution/10")
    akfix = await db.find_category("AKFIX")
    await db.update_product_fields(stapler.id, category_id=akfix.id)

    async with make_client(PAGE_HTML, []) as client:
        await import_channel(db, tmp_path / "media", client=client)

    assert (await db.get_product_by_id(lamp.id)).category.name == "TESS"
    assert (await db.get_product_by_id(stapler.id)).category.name == "AKFIX"
    assert await db.find_category("Yoritish") is None  # bo'shab qolgan eski kategoriya o'chirildi
