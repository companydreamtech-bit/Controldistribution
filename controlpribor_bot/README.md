# CONTROL PRIBOR - Telegram Bot & Catalog Scraper

Ushbu loyiha O'zbekistondagi sanoat elektrotexnikasi, avtomatika va KIPiA uskunalari sotuvchi **"CONTROL PRIBOR"** (https://controlpribor.uz) kompaniyasi uchun ishlab chiqilgan to'liq asinxron Python (Aiogram 3.x) Telegram boti va veb-sayt katalogi parseri hisoblanadi.

---

## 🌟 Asosiy Imkoniyatlar

1. **Sayt Skaneri (`scraper.py`):**
   - Glotr.uz platformasida ishlovchi katalogdan asinxron tarzda (`httpx` + `BeautifulSoup4`) toifalar va tovarlarni yig'adi.
   - Saytning muddati o'tgan SSL sertifikatini xavfsiz chetlab o'tadi (`verify=False`).
   - Tovar nomlaridagi kalit so'zlar bo'yicha eng mashhur 16 ta brendni (Fluke, Chint, Akfix, Mastech, UNI-T, Testo, RGK, Victor, Trotec, Michell, АКИП, ОВЕН, CEM, Мегеон, Sonel, APPA) avtomatik aniqlaydi.
   - Barcha ma'lumotlarni SQLite (`database.db`) bazasiga yozadi va zaxira sifatida `products_catalog.xlsx` fayliga eksport qiladi.

2. **100% Telegram Menyularida Ishlovchi Bot:**
   - Hech qanday tashqi havola/redirect yo'q — barcha xarid va navigatsiya to'liq Telegram ichida.
   - **Ro'yxatdan o'tish (FSM):** Ism-familiya va `request_contact=True` orqali telefon raqam olish.
   - **Brendlar bo'limi:** 16 ta brend inline tugmalarda, brend tanlanganda uning toifalari va tovarlari.
   - **Kategoriyalar bo'limi:** Barcha toifalar bo'yicha tovarlar ro'yxati.
   - **Tovar kartochkasi:** Rasm, narx, tavsif, `[ ➖ ] [ soni ] [ ➕ ]`, `[ 🛒 Savatchaga qo'shish ]`.
   - **Tezkor qidiruv (Search):** 5 000 ta mahsulot ichidan tovar modeli yoki nomi bo'yicha pagination bilan tezkor topish.
   - **Savatcha (Cart):** Tanlangan tovarlar miqdorini o'zgartirish, o'chirish, jami summa hisob-kitobi.
   - **Buyurtma berish:** Buyurtmani tartibli ko'rinishda xodimlar Telegram guruhiga (`ORDER_GROUP_ID`) yuborish.

---

## 📁 Loyiha Tuzilishi

```text
controlpribor_bot/
├── .env.example           # Muhit o'zgaruvchilari namunasi
├── requirements.txt       # Bog'liqliklar ro'yxati
├── scraper.py             # Saytdan tovarlarni yig'uvchi asinxron skript
├── config.py              # Sozlamalar va .env yuklovchi modul
├── database/
│   ├── __init__.py
│   ├── models.py          # SQLAlchemy 2.0 Async modellari (7 ta jadval)
│   └── db_manager.py      # Ma'lumotlar bazasi asinxron boshqaruvchisi
├── keyboards/
│   ├── __init__.py
│   ├── default_kb.py      # Asosiy menyu (Reply Keyboard)
│   └── inline_kb.py       # Brendlar, toifalar, tovarlar va savatcha (Inline Keyboard)
├── handlers/
│   ├── __init__.py
│   ├── start.py           # Start va Ro'yxatdan o'tish (FSM)
│   ├── catalog.py         # Brendlar va toifalar navigatsiyasi
│   ├── search.py          # Tezkor qidiruv
│   ├── cart.py            # Savatcha va buyurtmani guruhga yo'naltirish
│   └── other.py           # Bog'lanish va qo'llanma
├── utils/
│   ├── __init__.py
│   └── pagination.py      # Dinamik sahifalash (Paginator)
├── bot.py                 # Botni ishga tushiruvchi asosiy fayl
└── README.md              # Qo'llanma
```

---

## 🚀 O'rnatish va Ishga Tushirish

### 1. Talablar
- Python 3.10 yoki undan yuqori versiya.

### 2. Virtual Muhitni Yaratish va Faollashtirish
```bash
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# Linux / MacOS:
source venv/bin/activate
```

### 3. Kutubxonalarni O'rnatish
```bash
pip install -r controlpribor_bot/requirements.txt
```

### 4. Sozlamalarni Konfiguratsiya Qilish (`.env`)
`controlpribor_bot/.env.example` faylidan nusxa olib, `.env` faylini yarating:
```bash
cp controlpribor_bot/.env.example controlpribor_bot/.env
```
Fayl ichiga o'z ma'lumotlaringizni kiriting:
```ini
# BotFather bergan token:
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ

# Buyurtmalar tushadigan xodimlar Telegram guruhi ID raqami:
ORDER_GROUP_ID=-1001234567890

# Baza fayli:
DB_NAME=database.db

# Do'kon sayti manzili:
BASE_URL=https://controlpribor.uz
```

---

## 📥 Saytdan Mahsulotlarni Yig'ish (Scraper)

Saytdagi barcha toifalar va tovarlarni avtomatik skanerlab, bazaga yozish va Excel fayl yaratish uchun:
```bash
python -m controlpribor_bot.scraper
```
Bu skript:
1. `controlpribor.uz/categories/` sahifasidan barcha toifalarni aniqlaydi.
2. Sahifalarni aylanib chiqib, tovarlarni yig'adi.
3. Top 16 brendni avtomatik biriktiradi.
4. `database.db` ga to'liq ma'lumotlarni yozadi.
5. `products_catalog.xlsx` nomli Excel fayl yaratadi.

---

## 🤖 Telegram Botni Ishga Tushirish

```bash
python -m controlpribor_bot.bot
```

Bot ishga tushgach:
1. Telegramda botingizga `/start` yuboring.
2. Ism-familiyangizni kiriting va telefon raqamingizni yuboring.
3. Asosiy menyudan tovarlarni ko'ring, brendlar yoki qidiruv orqali toping, savatchaga qo'shing va buyurtma bering!
