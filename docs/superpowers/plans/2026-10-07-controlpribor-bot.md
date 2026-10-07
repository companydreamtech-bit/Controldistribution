# Control Pribor Telegram Bot & Catalog Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O'zbekistondagi sanoat elektrotexnikasi va KIPiA uskunalari sotuvchi "CONTROL PRIBOR" kompaniyasi uchun to'liq ishlaydigan asinxron scraper (`scraper.py`), SQLite ma'lumotlar bazasi va Aiogram 3.x Telegram botini yaratish.

**Architecture:** Modulli arxitektura: ma'lumotlar bazasi modeli va menejeri (`SQLAlchemy 2.0 Async + aiosqlite`), ko'p oqimli asinxron scraper (`aiohttp/httpx + bs4`), foydalanuvchi interfeysi uchun Aiogram 3.x routerlariga bo'lingan handlerlar (`start`, `catalog`, `search`, `cart`, `other`), qulay inline pagination utiliti.

**Tech Stack:** Python 3.10+, Aiogram 3.15, SQLAlchemy 2.0 (Async), aiosqlite, aiohttp / httpx, BeautifulSoup4, openpyxl, python-dotenv, pytest, pytest-asyncio.

**Spec:** [docs/superpowers/specs/2026-10-07-controlpribor-bot-design.md](file:///c:/Users/iqbol/OneDrive/Desktop/conrol/docs/superpowers/specs/2026-10-07-controlpribor-bot-design.md)

## Global Constraints

- Python versiyasi: Python 3.10+
- Bot freymvorki: Aiogram 3.x
- Botdan tashqariga hech qanday tashqi veb-sayt havolasi (redirect) berilmaydi; barcha navigatsiya va xarid 100% Telegram ichida amalga oshiriladi.
- controlpribor.uz saytida SSL sertifikat muddati o'tgan bo'lgani sababli parserda `verify=False` / unverified SSL konteksti qo'llaniladi.
- Top 16 brend avtomatik aniqlanadi, qolganlari "Boshqa brendlar" toifasiga joylanadi.
- Loyiha papka strukturasi aniq `controlpribor_bot/` modulli katalogi ko'rinishida bo'ladi.

## Review Focus

1. Sayt sahifalari va toifalarni skanerlashda SSL xatosi yoki tarmoq uzilishlari yuz berganda xavfsiz qayta urinish (retry/timeout).
2. Tovar nomlarida narx formati har xil ("1 200 000 сум", "По запросу", "Kelishilgan holda") bo'lganda narxni to'g'ri qayta ishlash.
3. 5000 ta mahsulot ichidan tezkor qidiruv so'rovi (masalan raqam `303`, model `MY-64`, matn `klesh`) yuborilganda SQLite tezkor ishlashi va bo'sh natijalarni to'g'ri ko'rsatish.
4. Savatchada mahsulot soni 1 dan kamaytirilganda avtomatik o'chirish yoki tasdiqlash so'rash.
5. Telegram guruhga buyurtma xabari jo'natilganda Markdown/HTML formatidagi maxsus belgilarni (masalan `<`, `>`, `&`) xavfsiz escape qilish.

---

### Task 1: Loyiha Asosi, Konfiguratsiya va Muhit Sozlamalari

**Files:**
- Create: `controlpribor_bot/.env.example`
- Create: `controlpribor_bot/requirements.txt`
- Create: `controlpribor_bot/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` klassi (`BOT_TOKEN`, `ORDER_GROUP_ID`, `DB_NAME`, `BASE_URL`)

- [ ] **Step 1: Write test for configuration loading**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `.env.example`, `requirements.txt`, and `config.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 2: Ma'lumotlar Bazasi Tuzilishi va Asinxron Menejer

**Files:**
- Create: `controlpribor_bot/database/__init__.py`
- Create: `controlpribor_bot/database/models.py`
- Create: `controlpribor_bot/database/db_manager.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Produces: `User`, `Brand`, `Category`, `Product`, `Cart`, `Order`, `OrderItem` modellari
- Produces: `DatabaseManager` klassi:
  - `init_db()`
  - `get_or_create_user(telegram_id, full_name, phone_number)`
  - `get_brands()`
  - `get_categories_by_brand(brand_id)`
  - `get_all_categories()`
  - `get_products_by_category(category_id, page, limit)`
  - `get_products_by_brand(brand_id, page, limit)`
  - `search_products(query, page, limit)`
  - `get_product_by_id(product_id)`
  - `add_to_cart(user_id, product_id, quantity)`
  - `get_cart(user_id)`
  - `update_cart_quantity(cart_id, quantity)`
  - `remove_from_cart(cart_id)`
  - `clear_cart(user_id)`
  - `create_order(user_id, total_price, items)`

- [ ] **Step 1: Write database unit and integration tests**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `models.py` and `db_manager.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 3: Sayt Parseri (`scraper.py`) va Excel Eksporti

**Files:**
- Create: `controlpribor_bot/scraper.py`
- Test: `tests/test_scraper.py`

**Interfaces:**
- Consumes: `DatabaseManager`, `Product`, `Category`, `Brand` from Task 2
- Produces: `ControlPriborScraper` klassi:
  - `fetch_page(url)` (SSL unverified bilan xavfsiz yuklash)
  - `parse_categories()`
  - `parse_products_from_category(category_url)`
  - `identify_top_brands(products)`
  - `save_to_db(products)`
  - `export_to_excel(products, filename="products_catalog.xlsx")`
  - `run()` (Asosiy skanerlash sikli)

- [ ] **Step 1: Write scraper unit tests with mocked HTML fixtures**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `scraper.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 4: Klaviaturalar va Pagination Utiliti

**Files:**
- Create: `controlpribor_bot/utils/__init__.py`
- Create: `controlpribor_bot/utils/pagination.py`
- Create: `controlpribor_bot/keyboards/__init__.py`
- Create: `controlpribor_bot/keyboards/default_kb.py`
- Create: `controlpribor_bot/keyboards/inline_kb.py`
- Test: `tests/test_keyboards.py`

**Interfaces:**
- Produces:
  - `main_menu_keyboard()`
  - `contact_keyboard()`
  - `brands_keyboard(brands, page)`
  - `categories_keyboard(categories, brand_id, page)`
  - `products_list_keyboard(products, page, total_pages, category_id, brand_id)`
  - `product_card_keyboard(product_id, quantity, category_id, brand_id)`
  - `cart_keyboard(cart_items)`
  - `Paginator` utiliti sinfi

- [ ] **Step 1: Write keyboard and pagination tests**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `pagination.py`, `default_kb.py` and `inline_kb.py`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 5: Bot Handlerlari (FSM Start, Katalog, Qidiruv, Savatcha, Guruhga Buyurtma)

**Files:**
- Create: `controlpribor_bot/handlers/__init__.py`
- Create: `controlpribor_bot/handlers/start.py` (FSM ro'yxatdan o'tish)
- Create: `controlpribor_bot/handlers/catalog.py` (Brendlar va toifalar)
- Create: `controlpribor_bot/handlers/search.py` (5000 tovar uchun tezkor qidiruv)
- Create: `controlpribor_bot/handlers/cart.py` (Savatcha va guruhga buyurtma)
- Create: `controlpribor_bot/handlers/other.py` (Aloqa / Bog'lanish)
- Test: `tests/test_handlers.py`

**Interfaces:**
- Consumes: `db_manager`, `keyboards`, `utils`, `config`
- Produces: Aiogram `Router` modullari

- [ ] **Step 1: Write tests for bot handler flows**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement all handlers**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Commit**

---

### Task 6: Bot Asosiy Ishga Tushirish Fayli (`bot.py`) va Hujjatlashtirish

**Files:**
- Create: `controlpribor_bot/bot.py`
- Create: `controlpribor_bot/README.md`
- Test: `tests/test_bot_setup.py`

**Interfaces:**
- Consumes: Barcha handlerlar, `db_manager`, `config`
- Produces: `main()` async entrypoint

- [ ] **Step 1: Write test for bot initialization and router registration**
- [ ] **Step 2: Run test to verify it fails**
- [ ] **Step 3: Implement `bot.py` and comprehensive `README.md`**
- [ ] **Step 4: Run test to verify it passes**
- [ ] **Step 5: Verify scraper and bot end-to-end integration**
- [ ] **Step 6: Commit**
