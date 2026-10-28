"""@asfdistribution Telegram kanalidagi postlardan tovarlarni rasmlari bilan import qilish.

Kanalning ochiq veb-ko'rinishi (https://t.me/s/<kanal>) o'qiladi, har bir tovar posti:
nom, brend, kategoriya, narx, tavsif va rasmga ajratiladi. Rasmlar lokal "media/" papkaga
yuklanadi. Tovar post havolasi (product_url) bo'yicha aniqlanadi, shuning uchun importni
qayta ishga tushirish xavfsiz: yangi postlar qo'shiladi, mavjudlarining narxi va tavsifi yangilanadi
(admin o'zgartirgan nom, brend va kategoriya saqlanib qoladi).

Ishga tushirish:
    python -m controlpribor_bot.channel_import            # import qilish
    python -m controlpribor_bot.channel_import --dry-run  # faqat nima import bo'lishini ko'rsatish
"""
import argparse
import asyncio
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

# Loyiha ildiz papkasini sys.path ga qo'shish
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import httpx
from bs4 import BeautifulSoup

from controlpribor_bot.database.db_manager import (
    DatabaseManager,
    OTHER_PRODUCTS_CATEGORY,
    SHOP_CATEGORIES,
)

logger = logging.getLogger(__name__)

DEFAULT_CHANNEL = "asfdistribution"
MEDIA_PREFIX = "media/"
# Tovar turi aniqlanmaganda (va 16 ta kategoriyaga mos kelmaganda) ishlatiladi
OTHER_CATEGORY = OTHER_PRODUCTS_CATEGORY
SHOP_CATEGORY_KEYS = {name.lower() for name in SHOP_CATEGORIES}

# Matnidan aniqlab bo'lmaydigan postlar uchun qo'lda tekshirilgan ma'lumotlar (rasm bo'yicha).
# Bu qiymatlar mavjud tovarlarga ham har importda qo'llanadi.
POST_OVERRIDES: Dict[int, Dict[str, str]] = {
    306: {"name": "VOLT LED lampochka (20W–50W)", "brand": "Volt", "category": OTHER_PRODUCTS_CATEGORY},
    330: {"name": "Пилки для электролобзика", "category": "Instrumentlar"},
}

# Kanondagi brend nomi -> postlarda uchraydigan yozilishlari
BRAND_ALIASES: Dict[str, List[str]] = {
    "Akfix": ["AKFIX"],
    "Terafix": ["TERAFIX"],
    "Tess": ["TESS"],
    "Nilson": ["NILSON"],
    "Oydin Electric": ["OYDIN ELECTRIC", "ODEA"],
    "Nura Electric": ["NURA ELECTRIC", "NURA LIGHT", "NURA"],
    "Chint": ["CHINT"],
    "Baumann Electric": ["BAUMANN ELECTRIC", "BAUMANN"],
    "Procab": ["PROCAB"],
    "Uzkabel": ["UZKABEL"],
    "Lezard": ["LEZARD"],
    "Redray": ["REDRAY"],
    "Profmet": ["PROFMET"],
    "Vini Tape": ["VINI TAPE", "VINI-TAPE"],
    "Layton": ["LAYTON"],
    "Mutlusan": ["MUTLUSAN"],
    "Wago": ["WAGO"],
    "Balance": ["BALANCE"],
    "Smash": ["SMASH"],
    "Xite": ["XITE"],
    "Wanruishi": ["WANRUISHI"],
    "Sobsan": ["SOBSAN"],
    "SAM": ["SAM ZAVOD"],
    "Krokodil": ["KROKODIL"],
}

# Tovar turi bo'yicha kategoriyalar: tartib muhim, birinchi mos kelgani tanlanadi.
# Kalit so'zlar so'z boshidan qidiriladi (masalan "щит" — "защита" ga mos kelmaydi).
CATEGORY_RULES: List[Tuple[str, List[str]]] = [
    ("Stabilizatorlar", ["стабилизатор", "stabilizator"]),
    ("Ventilyatsiya", ["вентил", "ventil"]),
    ("Metall shitlar", ["щит металл", "металлический щит", "metall shit", "щмп"]),
    ("gofra va korp", ["гофр", "gofr", "perfokorp", "короб", "kabel kanal", "металлорукав", "metallorukav"]),
    ("Kabellar", ["кабел", "kabel", "пугнп", "пвс", "apunp", "провод"]),
    ("Avtomatika va himoya", [
        "автомат", "avtomat", "узо", "uzo", "диф", "контактор", "рубильник", "rele", "реле",
        "abp", "авр", "nxb", "nb1", "dz158", "nl1", "nxm", "njr", "tm-1", "sp8", "датчик",
        "datchik", "фотосенсор", "сенсор", "taymer", "таймер", "nwu",
    ]),
    ("Montaj aksessuarlari", [
        "щит", "shit", "шина", "shina", "klemma", "клемм", "podrozetnik", "подрозетник",
        "бокс", "patron", "патрон", "изолент", "izolent", "tape",
    ]),
    ("Yoritish", [
        "lamp", "ламп", "led", "panel", "панел", "прожектор", "projektor", "prozhektor",
        "светильник", "plafon", "плафон", "фонар", "fonar", "slim", "трек", "milan",
        "yoritish", "chiroq",
    ]),
    ("Rozetka va o'chirgichlar", [
        "розетк", "rozetk", "выкл", "o'chirgich", "klavish", "kolodk", "колодк", "udilinitel",
        "udlinitel", "удлинит", "touran", "themis", "unique", "odea",
    ]),
    ("Germetik va qurilish kimyosi", [
        "герметик", "germetik", "силикон", "silikon", "пена", "ko'pik", "клей", "adhesive",
        "yopisht", "fuga", "фуга", "спрей", "dolgu", "tozalagich", "cleaner",
    ]),
    ("SAM shlanglar", ["shlang", "шланг"]),
    ("Instrumentlar", [
        "бур", "сверл", "пил", "нож", "рулетк", "заклёп", "заклеп", "насадк", "плоскогуб",
        "валик", "кисточк", "шпател", "kluch", "ключ", "звёздоч", "звездоч", "перк", "коронк",
        "кусачк", "утконос", "степлер", "диск", "лобзик", "электролобзик",
    ]),
]

# Kalit so'z topilmasa — brend bo'yicha kategoriya
BRAND_DEFAULT_CATEGORY: Dict[str, str] = {
    "Akfix": "Germetik va qurilish kimyosi",
    "Terafix": "Germetik va qurilish kimyosi",
    "Sobsan": "Germetik va qurilish kimyosi",
    "Procab": "Kabellar",
    "Uzkabel": "Kabellar",
    "Redray": "Yoritish",
    "Lezard": "Yoritish",
    "Tess": "Yoritish",
    "Chint": "Avtomatika va himoya",
    "Nilson": "Rozetka va o'chirgichlar",
    "Vini Tape": "Montaj aksessuarlari",
    "Smash": "Instrumentlar",
    "Xite": "Instrumentlar",
    "Wanruishi": "Instrumentlar",
    "Krokodil": "Instrumentlar",
}

# --- Botdagi 16 ta kategoriya ("📦 Tovarlar") ---
# Tovar turi bo'yicha aniq mos keladigan kategoriyalar (brenddan ustun: "Щит металл — Profmet")
SHOP_TYPE_FIRST = {"Metall shitlar", "gofra va korp"}
# Brend kategoriyalari
BRAND_TO_SHOP_CATEGORY: Dict[str, str] = {
    "Akfix": "AKFIX",
    "Terafix": "TERAFIX",
    "Tess": "TESS",
    "Nilson": "NILSON",
    "Oydin Electric": "OYDIN ELECTRIC",
    "Nura Electric": "NURA ELECTRIC",
    "Chint": "CHINT",
    "Baumann Electric": "BAUMANN ELECTRIC",
    "Procab": "PROCAB",
    "Uzkabel": "UZKABEL",
    "Lezard": "LEZARD",
    "SAM": "SAM shlanglar",
    "Profmet": "Metall shitlar",
    "Mutlusan": "gofra va korp",
}
# Brendi ro'yxatda bo'lmasa, tur bo'yicha
SHOP_TYPE_LATER = {"Instrumentlar", "SAM shlanglar"}
# Oldingi versiya yaratgan tur kategoriyalari — bo'shab qolsa o'chiriladi
LEGACY_TYPE_CATEGORIES = [name for name, _ in CATEGORY_RULES if name.lower() not in SHOP_CATEGORY_KEYS]


def shop_category(kind: str, brand: Optional[str]) -> str:
    """Tovar turi va brendidan botdagi 16 ta kategoriyadan birini tanlash, mos kelmasa — "Boshqa tovarlar"."""
    if kind in SHOP_TYPE_FIRST:
        return kind
    if brand in BRAND_TO_SHOP_CATEGORY:
        return BRAND_TO_SHOP_CATEGORY[brand]
    if kind in SHOP_TYPE_LATER:
        return kind
    return OTHER_PRODUCTS_CATEGORY

# Tovar bo'lmagan postlar (aksiya, e'lon, xizmat xabarlari)
SKIP_PATTERNS = [
    "pinned", "channel created", "aksiya", "акция", "start berdik", "farqini bilasizmi",
    "hamkor", "ishlab chiqaruvchi brend", "барча товарлари наличида",
]

# Kontakt va xizmat shartlari qatorlari (tavsifga kirmaydi)
NOISE_PREFIXES = (
    "📞", "📲", "☎", "📥", "📧", "📩", "📱", "📍", "🇺🇿", "🛒", "🚖", "🚚", "🔤", "#", "---",
)
NOISE_PATTERNS = [
    re.compile(r"^\+?[\d\s()/-]{9,}$"),  # faqat telefon raqami
    re.compile(r"улгуржи савдо|ulgurji savdo|^📦\s*mavjud$", re.IGNORECASE),
]

USD_RE = re.compile(
    r"\$\s*(\d{1,3}(?:[  ]\d{3})+|\d+)(?:[.,](\d+))?"
    r"|(\d{1,3}(?:[  ]\d{3})+|\d+)(?:[.,](\d+))?\s*\$"
)
SUM_RE = re.compile(r"(\d[\d . ]*\d|\d)\s*(?:сум|so'm|som)\b", re.IGNORECASE)
# "— 1,35" narxi: tiredan oldin bo'sh joy shart ("NC1-9511" model kodi narx emas)
TRAILING_NUMBER_RE = re.compile(r"\s[—–-]\s*(\d+(?:[.,]\d+)?)\s*\$?\s*$")
PRICE_LINE_RE = re.compile(
    r"(\d[\d.,]*\s*\$|\$\s*\d|\d\s*(?:сум|so'm)|\s[—–-]\s*\d+(?:[.,]\d+)?\s*$)", re.IGNORECASE
)
TITLE_SPLIT_RE = re.compile(r"\s[—–-]\s")


@dataclass
class ChannelPost:
    post_id: int
    text: str
    image_src: Optional[str]


@dataclass
class ParsedProduct:
    post_id: int
    name: str
    brand: Optional[str]
    category: str
    price: str
    description: str
    image_src: Optional[str]
    post_url: str
    needs_review: bool = False
    overridden: bool = False


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    images: int = 0
    products: List[ParsedProduct] = field(default_factory=list)

    @property
    def needs_review(self) -> List[ParsedProduct]:
        return [p for p in self.products if p.needs_review]


# --- Matnni tahlil qilish ---
def normalize(text: str) -> str:
    """Apostroflarni bir xil ko'rinishga keltirish (o‘, oʻ, o' -> o')."""
    return re.sub(r"[‘’ʻʼ`´]", "'", text)


def strip_decor(line: str) -> str:
    """Qator boshidagi emoji/belgilar va oxiridagi ❗, :, ! larni olib tashlash."""
    line = re.sub(r"^[^\w\"'«(]+", "", line)
    line = re.sub(r"[\s❗‼️!:.️]+$", "", line)
    return line.strip()


def clean_lines(text: str) -> List[str]:
    """Kontakt, xizmat shartlari va bo'sh qatorlarsiz matn qatorlari."""
    result = []
    for raw in normalize(text).split("\n"):
        line = raw.strip()
        if not line or line.startswith(NOISE_PREFIXES):
            continue
        if any(p.search(line) for p in NOISE_PATTERNS):
            continue
        result.append(line)
    return result


def is_price_line(line: str) -> bool:
    return bool(PRICE_LINE_RE.search(line))


def variant_label(line: str) -> str:
    """'ПУГНП 2*1.5 - 6210 сум' -> 'ПУГНП 2*1.5'."""
    label = re.split(r"\s+[—–-]\s+|\s+-\s*(?=[\d$])", line, maxsplit=1)[0]
    label = strip_decor(label.lstrip("-").strip())
    # "- 0.17$" kabi qatorda nom qismi yo'q
    return "" if re.fullmatch(r"[\d\s.,$]*", label) else label


def _amount(int_part: str, frac: Optional[str]) -> float:
    value = int(re.sub(r"\D", "", int_part))
    return float(f"{value}.{frac}") if frac else float(value)


def format_usd(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}$"


def format_sum(value: int) -> str:
    return f"{value:,}".replace(",", " ") + " so'm"


def extract_price(lines: List[str]) -> str:
    """Postdagi narxlardan bitta narx yoki 'min – max' diapazon."""
    text = "\n".join(lines)
    usd = []
    for m in USD_RE.finditer(text):
        if m.group(1):
            usd.append(_amount(m.group(1), m.group(2)))
        else:
            usd.append(_amount(m.group(3), m.group(4)))
    if not usd:
        sums = [int(re.sub(r"\D", "", m.group(1))) for m in SUM_RE.finditer(text)]
        if sums:
            lo, hi = min(sums), max(sums)
            return format_sum(lo) if lo == hi else f"{format_sum(lo)} – {format_sum(hi)}"
        # "TOURAN Розетка Nilson — 1,35" kabi valyutasiz ro'yxatlar dollarda beriladi
        trailing = [m for m in (TRAILING_NUMBER_RE.search(line) for line in lines) if m]
        if len(trailing) >= 2:
            usd = [float(m.group(1).replace(",", ".")) for m in trailing]
    if not usd:
        return "Kelishilgan holda"
    lo, hi = min(usd), max(usd)
    return format_usd(lo) if lo == hi else f"{format_usd(lo)} – {format_usd(hi)}"


def _brand_pattern(alias: str) -> re.Pattern:
    return re.compile(r"(?<![\w])" + re.escape(alias) + r"(?![\w])", re.IGNORECASE)


def detect_brand(lines: List[str]) -> Optional[str]:
    """Brendni avval sarlavhadan, keyin '❗ BREND' qatorlaridan, keyin butun matndan qidirish."""
    candidates = lines[:1] + [l for l in lines[1:4] if "❗" in l or "✨" in l] + lines
    for line in candidates:
        best = None
        for brand, aliases in BRAND_ALIASES.items():
            for alias in aliases:
                m = _brand_pattern(alias).search(line)
                if m and (best is None or m.start() < best[0]):
                    best = (m.start(), brand)
        if best:
            return best[1]
    return None


def is_brand_only(text: str) -> bool:
    cleaned = strip_decor(text).upper()
    return any(cleaned == alias for aliases in BRAND_ALIASES.values() for alias in aliases)


def _labels_summary(lines: List[str], max_len: int = 55) -> str:
    """Variantlar ro'yxatidan qisqa nom: umumiy prefiks ("Контактор 3P NC1") yoki birinchi variantlar."""
    labels = [variant_label(l) for l in lines if is_price_line(l)]
    labels = [l for l in labels if l]
    if not labels:
        return ""
    if len(labels) > 1:
        prefix = os.path.commonprefix(labels)
        # Prefiks so'z o'rtasida tugasa, oxirgi to'liq bo'lakkacha qisqartiramiz ("ABP NDS2-1" -> "ABP NDS2")
        if any(len(l) > len(prefix) and l[len(prefix)].isalnum() for l in labels):
            prefix = re.sub(r"[^\s\-/(]*$", "", prefix)
        prefix = prefix.rstrip(" -/(,")
        tokens = prefix.split()
        # Model kodining bo'lagi ("Вентилятор NV") nomga kirmaydi
        if len(tokens) > 1 and len(tokens[-1]) <= 3 and not re.search(r"\d", tokens[-1]):
            prefix = " ".join(tokens[:-1])
        if len(prefix) >= 6:
            return prefix
    summary = labels[0]
    if len(summary) > max_len:
        summary = summary[:max_len].rsplit(" ", 1)[0]
    for label in labels[1:]:
        if len(summary) + len(label) + 3 > max_len:
            return summary + " …"
        summary += " / " + label
    return summary


def extract_name(lines: List[str]) -> Tuple[str, bool]:
    """Tovar nomi va uni admin tekshirishi kerakmi (nom taxminiy bo'lsa True)."""
    if not lines:
        return "", True

    first = lines[0]
    rest = lines[1:]

    # Savol bilan boshlangan post ("Nega aynan 915N?") — reklama maqolasi, tovar emas
    if first.rstrip().endswith("?"):
        return "", True

    # Shior bilan boshlangan post: "Kuchlanishdan himoyalaning!" + "CHINT TM-1 — ..."
    if not TITLE_SPLIT_RE.search(first) and first.rstrip().endswith(("!", "?")) and rest:
        if TITLE_SPLIT_RE.search(rest[0]):
            return extract_name(rest)

    if is_price_line(first):
        summary = _labels_summary(lines)
        return (f"Tovar — {summary}" if summary else "Tovar"), True

    parts = TITLE_SPLIT_RE.split(first, maxsplit=1)
    left = strip_decor(parts[0])
    raw_right = parts[1].strip() if len(parts) > 1 else ""
    right = strip_decor(raw_right)
    right_is_slogan = raw_right.endswith(("!", "?", "."))  # gap — shior, nom emas

    # Sarlavhadan keyingi, narxlardan oldingi sarlavha qatori ("Многожильные кабели ПУГНП:", "SLIM LED ❗")
    subtitle = ""
    if rest and not is_price_line(rest[0]) and rest[0].rstrip().endswith((":", "❗")):
        subtitle = strip_decor(rest[0])

    if is_brand_only(left):
        if right and re.search(r"\d", right):
            return f"{left} {right}", False
        if subtitle:
            return f"{left} — {subtitle}", False
        if right:
            return f"{left} — {right}", False
        summary = _labels_summary(lines)
        return (f"{left} — {summary}" if summary else left), not summary

    name = left
    # Qisqa tavsifiy qism nomga qo'shiladi ("CHINT NXB-63 — AVTOMATIK O'CHIRGICH"), shiorlar emas
    if right and not right_is_slogan and len(right) <= 45:
        name = f"{left} — {right}"
    elif subtitle:
        name = f"{left} — {subtitle}"
    if len(left) < 3:
        return name or "Tovar", True
    # Kichik harf bilan boshlangan nom ("для электролобзика") — davomi bo'lgan post, tekshirish kerak
    return name, name[:1].islower()


def detect_category(name: str, lines: List[str], brand: Optional[str]) -> str:
    """Kategoriya: avval nomdan, keyin butun matndan kalit so'z, oxirida brend bo'yicha."""
    for text in (name, "\n".join(lines)):
        lowered = normalize(text).lower()
        for category, keywords in CATEGORY_RULES:
            if any(re.search(r"(?<![\w])" + re.escape(kw), lowered) for kw in keywords):
                return category
    if brand and brand in BRAND_DEFAULT_CATEGORY:
        return BRAND_DEFAULT_CATEGORY[brand]
    return OTHER_CATEGORY


def parse_post(post: ChannelPost, channel: str = DEFAULT_CHANNEL) -> Optional[ParsedProduct]:
    """Postni tovarga aylantirish; tovar bo'lmasa None."""
    raw = normalize(post.text).strip()
    if not raw:
        return None
    lowered = raw.lower()
    if any(p in lowered for p in SKIP_PATTERNS):
        return None

    lines = clean_lines(raw)
    if not lines:
        return None

    name, needs_review = extract_name(lines)
    if not name or name.endswith("?"):
        return None

    brand = detect_brand(lines)
    # "Розетка, выключатели и бошкалар" + "❗ NILSON" -> nomga brendni qo'shamiz
    if brand and not any(_brand_pattern(a).search(name) for a in BRAND_ALIASES[brand]):
        name = f"{name} — {brand}"
    price = extract_price(lines)
    kind = detect_category(name, lines, brand)

    # Brendi, narxi va turi aniqlanmagan post — tovar emas (masalan, umumiy e'lon)
    if not brand and price == "Kelishilgan holda" and kind == OTHER_CATEGORY:
        return None
    if kind == OTHER_CATEGORY:
        needs_review = True
    category = shop_category(kind, brand)

    # Tavsif: sarlavhadan keyingi qatorlar (tovar kartasida ko'rinadi)
    description = "\n".join(lines[1:]).strip() or None

    product = ParsedProduct(
        post_id=post.post_id,
        name=name[:200],
        brand=brand,
        category=category,
        price=price,
        description=description,
        image_src=post.image_src,
        post_url=f"https://t.me/{channel}/{post.post_id}",
        needs_review=needs_review,
    )
    override = POST_OVERRIDES.get(post.post_id) if channel == DEFAULT_CHANNEL else None
    if override:
        product.name = override.get("name", product.name)
        product.brand = override.get("brand", product.brand)
        product.category = override.get("category", product.category)
        product.needs_review = False
        product.overridden = True
    return product


# --- Kanal sahifalarini o'qish ---
def _style_url(style: str) -> Optional[str]:
    m = re.search(r"url\(['\"]?([^'\")]+)['\"]?\)", style or "")
    return m.group(1) if m else None


def parse_channel_page(html: str) -> List[ChannelPost]:
    soup = BeautifulSoup(html, "html.parser")
    posts = []
    for msg in soup.select(".tgme_widget_message[data-post]"):
        try:
            post_id = int(msg["data-post"].rsplit("/", 1)[-1])
        except ValueError:
            continue

        text_el = msg.select_one(".tgme_widget_message_text")
        text = ""
        if text_el:
            for br in text_el.find_all("br"):
                br.replace_with("\n")
            text = text_el.get_text()

        image_src = None
        media = msg.select_one(".tgme_widget_message_photo_wrap") or msg.select_one(
            ".tgme_widget_message_video_thumb"
        )
        if media:
            image_src = _style_url(media.get("style", ""))

        posts.append(ChannelPost(post_id=post_id, text=text, image_src=image_src))
    return posts


async def fetch_channel_posts(
    client: httpx.AsyncClient, channel: str = DEFAULT_CHANNEL, max_pages: int = 60
) -> List[ChannelPost]:
    """Kanalning barcha ochiq postlarini (yangidan eskiga sahifalab) o'qish."""
    posts: Dict[int, ChannelPost] = {}
    before: Optional[int] = None
    for _ in range(max_pages):
        url = f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")
        resp = await client.get(url)
        resp.raise_for_status()
        page = parse_channel_page(resp.text)
        if not page:
            break
        for p in page:
            posts[p.post_id] = p
        oldest = min(p.post_id for p in page)
        if before is not None and oldest >= before:
            break
        before = oldest
        if oldest <= 1:
            break
    return [posts[k] for k in sorted(posts)]


# --- Import ---
async def _download_image(client: httpx.AsyncClient, src: str, target: Path) -> bool:
    try:
        resp = await client.get(src)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("Rasm yuklanmadi %s: %s", src, e)
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(resp.content)
    return True


async def _unique_name(db: DatabaseManager, product: ParsedProduct, used: set) -> str:
    """Bir xil nomli tovarlar ("Заклёпка аппарат" x2) birinchi variant bilan farqlanadi."""
    lines = clean_lines(product.description or "")
    label = next((variant_label(l) for l in lines if is_price_line(l) and variant_label(l)), "")
    # Nomda bor so'zlarni va qavsdagi izohlarni tashlab, 3 so'zgacha qoldiramiz
    name_words = set(product.name.lower().split())
    label_words = [w for w in re.sub(r"\([^)]*\)", "", label).split() if w.lower() not in name_words][:3]
    label = " ".join(label_words)
    candidates = [product.name]
    if label:
        candidates.append(f"{product.name} {label}")
    candidates.append(f"{product.name} (#{product.post_id})")
    for name in candidates:
        if name.lower() not in used and not await db.get_product_by_name(name):
            return name
    return candidates[-1]


async def import_channel(
    db: DatabaseManager,
    media_dir: Path,
    channel: str = DEFAULT_CHANNEL,
    client: Optional[httpx.AsyncClient] = None,
    dry_run: bool = False,
    progress: Optional[Callable[[str], Awaitable[None]]] = None,
) -> ImportResult:
    """Kanal postlarini o'qib, tovarlarni bazaga qo'shish/yangilash.

    Rasmlar media_dir ga "asf_<post_id>.jpg" nomi bilan saqlanadi, bazada esa "media/asf_<id>.jpg"
    nisbiy yo'li yoziladi (bot uni baza papkasiga nisbatan topadi).
    """
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=30, follow_redirects=True)

    result = ImportResult()
    try:
        posts = await fetch_channel_posts(client, channel)
        if progress:
            await progress(f"Kanaldan {len(posts)} ta post o'qildi, tahlil qilinmoqda...")

        used_names: set = set()
        brand_ids: Dict[str, int] = {}
        category_ids: Dict[str, int] = {}

        async def brand_id_for(name: Optional[str]) -> Optional[int]:
            if not name:
                return None
            if name not in brand_ids:
                slug = re.sub(r"[\s_-]+", "-", re.sub(r"[^\w\s-]", "", name.lower())).strip("-")
                brand_ids[name] = (await db.add_brand(name, slug)).id
            return brand_ids[name]

        async def category_id_for(name: str) -> int:
            if name not in category_ids:
                category_ids[name] = (await db.add_category(name)).id
            return category_ids[name]

        for post in posts:
            product = parse_post(post, channel)
            if not product:
                result.skipped += 1
                continue

            existing = await db.get_product_by_url(product.post_url)
            if not existing and not product.overridden:
                product.name = await _unique_name(db, product, used_names)
            used_names.add(product.name.lower())
            result.products.append(product)
            if dry_run:
                continue

            image_url = existing.image_url if existing else None
            if product.image_src:
                rel_path = f"{MEDIA_PREFIX}asf_{product.post_id}.jpg"
                target = media_dir / Path(rel_path).name
                if not target.exists() and await _download_image(client, product.image_src, target):
                    result.images += 1
                if target.exists() and (not image_url or image_url.startswith(MEDIA_PREFIX)):
                    image_url = rel_path

            if existing:
                fields = {"image_url": image_url}
                # Kanalda narx/tavsif bo'lmasa, admin qo'lda kiritgani saqlanadi
                if product.price != "Kelishilgan holda":
                    fields["price"] = product.price
                if product.description:
                    fields["description"] = product.description
                if product.overridden:
                    # Qo'lda tekshirilgan nom/brend/kategoriya avval import qilingan tovarga ham qo'llanadi
                    fields.update(
                        name=product.name,
                        brand_id=await brand_id_for(product.brand),
                        category_id=await category_id_for(product.category),
                    )
                else:
                    # Do'kon kategoriyalaridan tashqaridagi (eski avtomatik) kategoriyadan ko'chirish;
                    # admin 16 tadan biriga qo'lda qo'ygan bo'lsa, tegilmaydi
                    current = await db.get_product_by_id(existing.id)
                    if not current.category or current.category.name.lower() not in SHOP_CATEGORY_KEYS:
                        fields["category_id"] = await category_id_for(product.category)
                await db.update_product_fields(existing.id, **fields)
                result.updated += 1
                continue

            await db.add_product(
                name=product.name,
                price=product.price,
                brand_id=await brand_id_for(product.brand),
                category_id=await category_id_for(product.category),
                image_url=image_url,
                description=product.description,
                product_url=product.post_url,
            )
            result.created += 1

        if not dry_run:
            await _remove_empty_legacy_categories(db)
    finally:
        if own_client:
            await client.aclose()
    return result


async def _remove_empty_legacy_categories(db: DatabaseManager) -> None:
    """Oldingi importlar yaratgan, endi bo'sh qolgan tur kategoriyalarini ("Yoritish", "Kabellar"...) o'chirish."""
    for name in LEGACY_TYPE_CATEGORIES:
        cat = await db.find_category(name)
        if cat and await db.count_products(category_id=cat.id) == 0:
            await db.delete_category(cat.id)


def default_media_dir(db_path: str) -> Path:
    return Path(db_path).resolve().parent / "media"


async def _main(dry_run: bool) -> None:
    from controlpribor_bot.config import Config

    try:
        db_path = Config.load().db_path
    except ValueError:
        # BOT_TOKEN shart emas: faqat baza yo'li kerak
        db_path = str(Path(__file__).resolve().parent / "database.db")

    db = DatabaseManager(f"sqlite+aiosqlite:///{db_path}")
    await db.init_db()

    async def log_progress(msg: str) -> None:
        logger.info(msg)

    try:
        result = await import_channel(db, default_media_dir(db_path), dry_run=dry_run, progress=log_progress)
    finally:
        await db.close()

    for p in result.products:
        mark = "⚠️ " if p.needs_review else ""
        print(f"{mark}#{p.post_id} | {p.name} | {p.brand or '-'} | {p.category} | {p.price}")
    print(
        f"\nTovarlar: {len(result.products)} (yangi: {result.created}, yangilangan: {result.updated}), "
        f"o'tkazib yuborilgan postlar: {result.skipped}, yuklangan rasmlar: {result.images}, "
        f"tekshirish kerak: {len(result.needs_review)}"
    )
    if dry_run:
        print("(--dry-run: bazaga hech narsa yozilmadi)")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Telegram kanalidan tovarlarni import qilish")
    parser.add_argument("--dry-run", action="store_true", help="Bazaga yozmasdan natijani ko'rsatish")
    asyncio.run(_main(parser.parse_args().dry_run))
