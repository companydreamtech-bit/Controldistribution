"""Brend va kategoriya tugmalari uchun mos emojilar."""

# Brend -> asosiy tovar turiga mos emoji
BRAND_ICONS = {
    "akfix": "🧴",
    "terafix": "🧴",
    "tytan": "🧴",
    "sobsan": "🧴",
    "baumann electric": "💡",
    "tess": "💡",
    "lezard": "💡",
    "redray": "💡",
    "oydin electric": "💡",
    "layton": "💡",
    "chint": "⚡",
    "nura electric": "⚡",
    "balance": "🔋",
    "nilson": "🔌",
    "procab": "🔗",
    "uzkabel": "🔗",
    "profmet": "🗄",
    "mutlusan": "➰",
    "wago": "🔩",
    "vini tape": "🩹",
    "sam": "💧",
    "smash": "🛠",
    "xite": "🛠",
    "wanruishi": "🛠",
    "krokodil": "🛠",
    # O'lchov asboblari
    "fluke": "📏",
    "mastech": "📏",
    "uni-t": "📏",
    "rgk": "📏",
    "victor": "📏",
    "testo": "🌡",
    "michell": "🌡",
    "trotec": "🌡",
    "акип": "📏",
    "овен": "🎛",
    "cem": "📏",
    "мегеон": "📏",
    "sonel": "📏",
    "appa": "📏",
}

# Tovar turi bo'yicha kategoriyalar
CATEGORY_ICONS = {
    "yoritish": "💡",
    "rozetka va o'chirgichlar": "🔌",
    "avtomatika va himoya": "⚡",
    "stabilizatorlar": "🔋",
    "ventilyatsiya": "🌬",
    "kabellar": "🔗",
    "gofra va korp": "➰",
    "metall shitlar": "🗄",
    "montaj aksessuarlari": "🔩",
    "germetik va qurilish kimyosi": "🧴",
    "instrumentlar": "🛠",
    "sam shlanglar": "💧",
    "boshqa tovarlar": "📦",
}

DEFAULT_BRAND_ICON = "🏷"
DEFAULT_CATEGORY_ICON = "📁"


def brand_icon(name: str) -> str:
    return BRAND_ICONS.get((name or "").strip().lower(), DEFAULT_BRAND_ICON)


def category_icon(name: str) -> str:
    """Kategoriya emojisi; "AKFIX" kabi brend nomli kategoriya brend emojisini oladi."""
    key = (name or "").strip().lower()
    return CATEGORY_ICONS.get(key) or BRAND_ICONS.get(key) or DEFAULT_CATEGORY_ICON
