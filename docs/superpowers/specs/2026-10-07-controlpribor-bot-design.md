# CONTROL PRIBOR - Telegram Bot & Scraper Arxitektura Spetsifikatsiyasi

- **Sana:** 2026-10-07
- **Loyiha nomi:** Control Pribor Telegram Bot & Catalog Scraper
- **Texnologiyalar:** Python 3.10+, Aiogram 3.15+, SQLAlchemy 2.0 (Async), aiosqlite, aiohttp / httpx, BeautifulSoup4, openpyxl, python-dotenv

---

## 1. Umumiy Maqsad va Talablar

"CONTROL PRIBOR" (https://controlpribor.uz) sanoat elektrotexnikasi va KIPiA uskunalari do'koni uchun:
1. Glotr.uz platformasidagi katalogdan tovarlar va toifalarni asinxron skanerlovchi `scraper.py` skripti.
2. 7 ta jadvalli SQLite ma'lumotlar bazasi (`database.db`).
3. Aiogram 3.x asosida ishlab chiqilgan, 100% Telegram menyulari ichida ishlovchi (tashqi saytga havolasiz), ro'yxatdan o'tish, brendlar, kategoriyalar, tezkor qidiruv, savatcha va buyurtmalarni Telegram guruhga yuborish imkoniyatiga ega Telegram bot.

---

## 2. Loyiha Fayl Tuzilishi

```text
controlpribor_bot/
├── .env.example
├── requirements.txt
├── scraper.py             # Saytdan tovar va brendlarni tortib bazaga yozuvchi skript
├── config.py              # Sozlamalar va .env yuklash
├── database/
│   ├── __init__.py
│   ├── models.py          # SQLAlchemy 2.0 Async modellari
│   └── db_manager.py      # Baza bilan asinxron operatsiyalar (CRUD)
├── keyboards/
│   ├── __init__.py
│   ├── default_kb.py      # Asosiy menyu Reply Keyboard tugmalari
│   └── inline_kb.py       # Brendlar, tovarlar, korzinka inline tugmalari
├── handlers/
│   ├── __init__.py
│   ├── start.py           # Ro'yxatdan o'tish (FSM) va /start
│   ├── catalog.py         # Brendlar va toifalar navigatsiyasi
│   ├── search.py          # Qidiruv logikasi (nom va model bo'yicha)
│   ├── cart.py            # Savatcha va buyurtma berish
│   └── other.py           # Bog'lanish va yordam
├── utils/
│   ├── __init__.py
│   └── pagination.py      # Tovarlar uchun pagination utiliti
├── bot.py                 # Asosiy bot ishga tushirish fayli
└── README.md              # O'rnatish va ishga tushirish yo'riqnomasi
```

---

## 3. Ma'lumotlar Bazasi Modeli (SQLAlchemy 2.0)

1. **`users`**:
   - `id`: Integer, Primary Key, autoincrement
   - `telegram_id`: BigInteger, unique, indexed
   - `full_name`: String(255)
   - `phone_number`: String(50)
   - `created_at`: DateTime(timezone=True), default=func.now()

2. **`brands`**:
   - `id`: Integer, Primary Key, autoincrement
   - `name`: String(100), unique
   - `slug`: String(100), unique

3. **`categories`**:
   - `id`: Integer, Primary Key, autoincrement
   - `name`: String(255)
   - `brand_id`: Integer, ForeignKey('brands.id'), nullable=True

4. **`products`**:
   - `id`: Integer, Primary Key, autoincrement
   - `brand_id`: Integer, ForeignKey('brands.id'), nullable=True
   - `category_id`: Integer, ForeignKey('categories.id'), nullable=True
   - `name`: String(500), indexed
   - `price`: String(100) (masalan: "1 200 000 so'm" yoki "Kelishilgan holda")
   - `price_raw`: Float (raqamli narx, tartiblash va hisob-kitob uchun, mavjud bo'lmasa 0)
   - `image_url`: Text, nullable=True
   - `description`: Text, nullable=True
   - `product_url`: Text, nullable=True

5. **`cart`**:
   - `id`: Integer, Primary Key, autoincrement
   - `user_id`: Integer, ForeignKey('users.id')
   - `product_id`: Integer, ForeignKey('products.id')
   - `quantity`: Integer, default=1

6. **`orders`**:
   - `id`: Integer, Primary Key, autoincrement
   - `user_id`: Integer, ForeignKey('users.id')
   - `total_price`: String(100)
   - `status`: String(50), default="Yangi" (Yangi, Qabul qilindi, Bekor qilindi)
   - `created_at`: DateTime(timezone=True), default=func.now()

7. **`order_items`**:
   - `id`: Integer, Primary Key, autoincrement
   - `order_id`: Integer, ForeignKey('orders.id')
   - `product_id`: Integer, ForeignKey('products.id')
   - `product_name`: String(500)
   - `quantity`: Integer
   - `price`: String(100)

---

## 4. Parser Mexanizmi (`scraper.py`)

1. **Sayt spetsifikatsiyasi:**
   - Asosiy domen: `https://controlpribor.uz`
   - SSL sertifikati muddati o'tgan bo'lgani sababli `ssl_context = ssl.create_default_context(); ssl_context.check_hostname = False; ssl_context.verify_mode = ssl.CERT_NONE` yoki `verify=False` bilan ulanish.
2. **Katalog tuzilishi:**
   - Glotr.uz platformasida toifalar `/categories/` sahifasida joylashgan.
   - Har bir toifaning tovarlar sahifasi: `/proposals/<slug>/` yoki `/category/<slug>/`.
   - Sahifalash: `?page=X` (sahifada tovarlar tugaguncha yoki oxirgi sahifagacha).
3. **Brendlarni avtomatik aniqlash:**
   - Tovar nomidagi kalit so'zlar: `FLUKE`, `CHINT`, `AKFIX`, `MASTECH`, `UNI-T`, `TESTO`, `RGK`, `VICTOR`, `TROTEC`, `MICHELL`, `АКИП`, `ОВЕН`, `MEGEON`, `CEM`, `SONEL`, `APPA`.
   - Eng ko'p uchraydigan 16 ta brend ro'yxati shakllanadi va `brands` jadvaliga kiritiladi.
   - Qolgan tovarlar "Boshqa brendlar" ga biriktiriladi.
4. **Zaxiralash:**
   - Ma'lumotlar bevosita SQLite bazasiga (`database.db`) yoziladi.
   - Barcha tovarlar `products_catalog.xlsx` fayliga ustunlar bilan eksport qilinadi:
     `ID`, `Nomi`, `Brend`, `Kategoriya`, `Narxi`, `Rasm URL`, `Tovar Havolasi`.

---

## 5. Telegram Bot (Aiogram 3.x) Arxitekturasi va UX/UI

1. **Start & Ro'yxatdan o'tish (FSM):**
   - Agar foydalanuvchi bazada bo'lmasa:
     - 1-qadam: "Assalomu alaykum! 'CONTROL PRIBOR' botiga xush kelibsiz. Iltimos, ism va familiyangizni kiriting:"
     - 2-qadam: `KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)` tugmasi chiqadi.
     - Telefon raqam olingach, ma'lumotlar bazaga yoziladi va asosiy menyu ochiladi.
   - Agar mavjud bo'lsa: darhol Asosiy menyu ko'rsatiladi.

2. **Asosiy Menyu (Reply Keyboard):**
   - 🏷 Brendlar | 📁 Barcha kategoriyalar
   - 🔍 Tovar qidirish | 🛒 Savatcha
   - 📞 Bog'lanish / Menejer

3. **Brendlar Bo'limi:**
   - 16 ta brend Inline tugmalarda chiqadi (2 qatordan, masalan: `[ FLUKE ] [ CHINT ]`).
   - Brend tanlanganda: ushbu brendga tegishli toifalar Inline chiqadi.
   - Toifa tanlanganda: tovarlar ro'yxati chiqadi.

4. **Tovar Kartochkasi & Pagination:**
   - Sahifada tovarlar ro'yxati yoki bitta tovar kartochkasi:
     - Tovar rasmi (agar bo'lsa), nomi, toifasi, narxi.
     - Inline tugmalar:
       `[ ➖ ] [ 1 ] [ ➕ ]`
       `[ 🛒 Savatchaga qo'shish ]`
       `[ ⬅️ Orqaga ]`

5. **Tezkor Qidiruv (Search):**
   - Foydalanuvchi qidiruv tugmasini bosib yoki to'g'ridan-to'g'ri tovar modeli/nomini yozganda (masalan: `303`, `DT-830`, `klesh`, `rele`):
   - SQLite `LIKE '%query%'` orqali 5000 tovar ichidan tezkor qidiriladi.
   - Natijalar pagination ko'rinishida taqdim etiladi (`⬅️ 1/5 ➡️`).

6. **Savatcha va Buyurtma:**
   - Savatchadagi har bir tovar: Nomi, soni, narxi, jami summa.
   - Tugmalar: Har bir tovar uchun `[ ❌ O'chirish ]`, `[ ➕ ] [ ➖ ]`.
   - `[ ✅ Buyurtmani tasdiqlash ]`, `[ 🗑 Savatchani tozalash ]`, `[ ⬅️ Bosh menyu ]`.
   - Tasdiqlanganda:
     - Guruhga (`ORDER_GROUP_ID`) buyurtma xabari yuboriladi.
     - Mijozga tabrik xabari yuborilib, savatcha tozalanadi.

---

## 6. Xavfsizlik va Barqarorlik

- `.env` orqali `BOT_TOKEN`, `ORDER_GROUP_ID`, `DB_NAME` yuklanadi.
- Bot xatoliklarini ushlash uchun Aiogram middleware va loglar (`logging`).
- Rasm yuklashda agar URL ishlamasa yoki bo'sh bo'lsa, xatolikka yo'l qo'ymasdan standart xabar sifatida yuborish.
