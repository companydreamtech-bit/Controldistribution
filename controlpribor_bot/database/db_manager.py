from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import case, event, select, update, delete, func, text, or_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from controlpribor_bot.database.models import (
    Base,
    User,
    Brand,
    Category,
    Product,
    Cart,
    Order,
    OrderItem,
)


DEFAULT_CATEGORIES = [
    "AKFIX",
    "TERAFIX",
    "TYTAN",
    "TESS",
    "NILSON",
    "OYDIN ELECTRIC",
    "NURA ELECTRIC",
    "CHINT",
    "BAUMANN ELECTRIC",
    "PROCAB",
    "UZKABEL",
    "gofra va korp",
    "Metall shitlar",
    "Instrumentlar",
    "SAM shlanglar",
    "LEZARD",
]
# 16 ta kategoriyaga mos kelmagan tovarlar uchun — "Tovarlar" ro'yxatining oxirida turadi
OTHER_PRODUCTS_CATEGORY = "Boshqa tovarlar"
SHOP_CATEGORIES = DEFAULT_CATEGORIES + [OTHER_PRODUCTS_CATEGORY]


# Kanaldagi asosiy brendlar (t.me/asfdistribution tavsifidagi tartibda) — ro'yxat boshida turadi
FEATURED_BRANDS = [
    "akfix",
    "chint",
    "baumann electric",
    "profmet",
    "nura electric",
    "nilson",
    "uzkabel",
    "procab",
]
OTHER_BRANDS_NAME = "boshqa brendlar"


def _unicode_lower(value):
    """SQLite LOWER() faqat lotin harflarini kichiklashtiradi; bu funksiya kirillni ham qamraydi."""
    return value.lower() if isinstance(value, str) else value

class DatabaseManager:
    def __init__(self, db_url: str = "sqlite+aiosqlite:///database.db"):
        self.engine = create_async_engine(db_url, echo=False)
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        # SQLite tashqi kalitlarni (ON DELETE SET NULL / CASCADE) faqat har bir ulanishda
        # PRAGMA foreign_keys yoqilganda bajaradi.
        # Katta-kichik harfsiz solishtirish: SQLite'da Python'ning str.lower orqali (kirill harflari uchun)
        self._lower = func.lower
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine.sync_engine, "connect", self._setup_sqlite_connection)
            self._lower = func.py_lower

    @staticmethod
    def _setup_sqlite_connection(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()
        dbapi_connection.create_function("py_lower", 1, _unicode_lower, deterministic=True)

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # SQLite tezkor ishlashini ta'minlash (WAL rejimi, kesh hajmi, xotirada saqlash)
            await conn.execute(text("PRAGMA journal_mode = WAL;"))
            await conn.execute(text("PRAGMA synchronous = NORMAL;"))
            await conn.execute(text("PRAGMA cache_size = 10000;"))
            await conn.execute(text("PRAGMA temp_store = MEMORY;"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand_id);"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category_id);"))
        await self.seed_default_categories()

    async def close(self):
        await self.engine.dispose()

    # --- Users ---
    async def get_or_create_user(
        self, telegram_id: int, full_name: str, phone_number: str
    ) -> Tuple[User, bool]:
        async with self.session_factory() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                return user, False

            new_user = User(
                telegram_id=telegram_id,
                full_name=full_name,
                phone_number=phone_number,
            )
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            return new_user, True

    async def update_user_phone(self, telegram_id: int, phone_number: str) -> Optional[User]:
        async with self.session_factory() as session:
            res = await session.execute(select(User).where(User.telegram_id == telegram_id))
            user = res.scalar_one_or_none()
            if not user:
                return None
            user.phone_number = phone_number
            await session.commit()
            await session.refresh(user)
            return user

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        async with self.session_factory() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    # --- Brands ---
    async def find_brand(self, name: str, slug: str, exclude_id: Optional[int] = None) -> Optional[Brand]:
        """Nomi (katta-kichik harfsiz) yoki slug'i mos keladigan brendni topish."""
        async with self.session_factory() as session:
            stmt = select(Brand).where(or_(self._lower(Brand.name) == name.lower(), Brand.slug == slug))
            if exclude_id is not None:
                stmt = stmt.where(Brand.id != exclude_id)
            res = await session.execute(stmt.limit(1))
            return res.scalar_one_or_none()

    async def add_brand(self, name: str, slug: str) -> Brand:
        existing = await self.find_brand(name, slug)
        if existing:
            return existing
        async with self.session_factory() as session:

            brand = Brand(name=name, slug=slug)
            session.add(brand)
            await session.commit()
            await session.refresh(brand)
            return brand

    async def get_brands(self) -> List[Brand]:
        """Asosiy brendlar tepada, qolganlari alifbo bo'yicha, "Boshqa brendlar" eng oxirida."""
        async with self.session_factory() as session:
            res = await session.execute(select(Brand))
            brands = list(res.scalars().all())

        def sort_key(brand: Brand):
            name = brand.name.strip().lower()
            if name in FEATURED_BRANDS:
                return (0, FEATURED_BRANDS.index(name), name)
            if name == OTHER_BRANDS_NAME:
                return (2, 0, name)
            return (1, 0, name)

        return sorted(brands, key=sort_key)

    async def get_brand_by_id(self, brand_id: int) -> Optional[Brand]:
        async with self.session_factory() as session:
            stmt = select(Brand).where(Brand.id == brand_id)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def update_brand(self, brand_id: int, name: str, slug: str) -> Optional[Brand]:
        """Brend nomini yangilash. Nom yoki slug band bo'lsa ValueError."""
        if await self.find_brand(name, slug, exclude_id=brand_id):
            raise ValueError("Bunday nomli brend allaqachon mavjud")
        async with self.session_factory() as session:
            brand = await session.get(Brand, brand_id)
            if not brand:
                return None
            brand.name = name
            brand.slug = slug
            await session.commit()
            await session.refresh(brand)
            return brand

    # --- Categories ---
    async def seed_default_categories(self) -> None:
        """Standart 16 ta kategoriyani bazaga kiritish (agar mavjud bo'lmasa)."""
        async with self.session_factory() as session:
            for cat_name in DEFAULT_CATEGORIES:
                stmt = select(Category).where(Category.name == cat_name)
                res = await session.execute(stmt)
                if not res.scalar_one_or_none():
                    session.add(Category(name=cat_name))
            await session.commit()

    async def find_category(self, name: str, exclude_id: Optional[int] = None) -> Optional[Category]:
        """Nomi (katta-kichik harfsiz) mos keladigan kategoriyani topish."""
        async with self.session_factory() as session:
            stmt = select(Category).where(self._lower(Category.name) == name.lower())
            if exclude_id is not None:
                stmt = stmt.where(Category.id != exclude_id)
            res = await session.execute(stmt.limit(1))
            return res.scalar_one_or_none()

    async def add_category(self, name: str, brand_id: Optional[int] = None) -> Category:
        existing = await self.find_category(name)
        if existing:
            return existing
        async with self.session_factory() as session:

            cat = Category(name=name, brand_id=brand_id)
            session.add(cat)
            await session.commit()
            await session.refresh(cat)
            return cat

    async def get_categories_by_brand(self, brand_id: int) -> List[Category]:
        async with self.session_factory() as session:
            stmt = (
                select(Category)
                .outerjoin(Product, Product.category_id == Category.id)
                .where((Category.brand_id == brand_id) | (Product.brand_id == brand_id))
                .distinct()
                .order_by(Category.name.asc())
            )
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def get_all_categories(self, limit: Optional[int] = None) -> List[Category]:
        async with self.session_factory() as session:
            stmt = select(Category).options(selectinload(Category.brand)).order_by(Category.id.asc())
            if limit:
                stmt = stmt.limit(limit)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def get_shop_categories(self) -> List[Category]:
        """"📦 Tovarlar" menyusi: 16 ta asosiy kategoriya belgilangan tartibda (bo'sh bo'lsa ham),
        keyin tovari bor boshqa kategoriyalar, "Boshqa tovarlar" eng oxirida."""
        order = {name.lower(): idx for idx, name in enumerate(DEFAULT_CATEGORIES)}
        other_key = OTHER_PRODUCTS_CATEGORY.lower()
        async with self.session_factory() as session:
            counts = dict(
                (await session.execute(
                    select(Product.category_id, func.count(Product.id)).group_by(Product.category_id)
                )).all()
            )
        result = []
        for cat in await self.get_all_categories():
            key = cat.name.strip().lower()
            if key in order:
                result.append(((0, order[key], key), cat))
            elif counts.get(cat.id):
                result.append(((2 if key == other_key else 1, 0, key), cat))
        return [cat for _, cat in sorted(result, key=lambda item: item[0])]

    async def get_category_by_id(self, category_id: int) -> Optional[Category]:
        async with self.session_factory() as session:
            stmt = select(Category).options(selectinload(Category.brand)).where(Category.id == category_id)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def update_category_fields(self, category_id: int, **kwargs) -> Optional[Category]:
        """Kategoriya maydonlarini yangilash (name, brand_id). Nom band bo'lsa ValueError."""
        if "name" in kwargs and await self.find_category(kwargs["name"], exclude_id=category_id):
            raise ValueError("Bunday nomli kategoriya allaqachon mavjud")
        async with self.session_factory() as session:
            cat = await session.get(Category, category_id)
            if not cat:
                return None
            for key, val in kwargs.items():
                if hasattr(cat, key):
                    setattr(cat, key, val)
            await session.commit()
        return await self.get_category_by_id(category_id)

    # --- Products ---
    async def add_product(
        self,
        name: str,
        price: str = "Kelishilgan holda",
        brand_id: Optional[int] = None,
        category_id: Optional[int] = None,
        image_url: Optional[str] = None,
        description: Optional[str] = None,
        product_url: Optional[str] = None,
    ) -> Product:
        async with self.session_factory() as session:
            stmt = select(Product).where(Product.name == name)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                existing.price = price
                existing.brand_id = brand_id
                existing.category_id = category_id
                existing.image_url = image_url or existing.image_url
                existing.description = description or existing.description
                existing.product_url = product_url or existing.product_url
                await session.commit()
                await session.refresh(existing)
                return existing

            product = Product(
                name=name,
                price=price,
                brand_id=brand_id,
                category_id=category_id,
                image_url=image_url,
                description=description,
                product_url=product_url,
            )
            session.add(product)
            await session.commit()
            await session.refresh(product)
            return product

    async def get_product_by_id(self, product_id: int) -> Optional[Product]:
        async with self.session_factory() as session:
            stmt = (
                select(Product)
                .options(selectinload(Product.brand), selectinload(Product.category))
                .where(Product.id == product_id)
            )
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def get_product_by_name(self, name: str) -> Optional[Product]:
        async with self.session_factory() as session:
            stmt = select(Product).where(self._lower(Product.name) == name.lower()).limit(1)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def get_product_by_url(self, product_url: str) -> Optional[Product]:
        async with self.session_factory() as session:
            stmt = select(Product).where(Product.product_url == product_url).limit(1)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    async def count_products(
        self, brand_id: Optional[int] = None, category_id: Optional[int] = None
    ) -> int:
        async with self.session_factory() as session:
            stmt = select(func.count(Product.id))
            if brand_id is not None:
                stmt = stmt.where(Product.brand_id == brand_id)
            if category_id is not None:
                stmt = stmt.where(Product.category_id == category_id)
            return (await session.execute(stmt)).scalar() or 0

    async def count_categories_of_brand(self, brand_id: int) -> int:
        async with self.session_factory() as session:
            stmt = select(func.count(Category.id)).where(Category.brand_id == brand_id)
            return (await session.execute(stmt)).scalar() or 0

    async def get_products_by_category(
        self, category_id: int, brand_id: Optional[int] = None, page: int = 1, limit: int = 6
    ) -> Tuple[List[Product], int]:
        offset = (page - 1) * limit
        async with self.session_factory() as session:
            count_stmt = select(func.count(Product.id)).where(Product.category_id == category_id)
            if brand_id:
                count_stmt = count_stmt.where(Product.brand_id == brand_id)
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = (
                select(Product)
                .options(selectinload(Product.brand), selectinload(Product.category))
                .where(Product.category_id == category_id)
            )
            if brand_id:
                stmt = stmt.where(Product.brand_id == brand_id)
            stmt = stmt.order_by(Product.name.asc()).offset(offset).limit(limit)
            res = await session.execute(stmt)
            return list(res.scalars().all()), total

    async def get_products_by_brand(
        self, brand_id: int, page: int = 1, limit: int = 6
    ) -> Tuple[List[Product], int]:
        offset = (page - 1) * limit
        async with self.session_factory() as session:
            count_stmt = select(func.count(Product.id)).where(Product.brand_id == brand_id)
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = (
                select(Product)
                .where(Product.brand_id == brand_id)
                .order_by(Product.id.desc())
                .offset(offset)
                .limit(limit)
            )
            res = await session.execute(stmt)
            return list(res.scalars().all()), total

    async def search_products(
        self, query: str, page: int = 1, limit: int = 6
    ) -> Tuple[List[Product], int]:
        """Nom va tavsif bo'yicha katta-kichik harfsiz qidiruv (variant kodlari tavsifda turadi).

        Nomida topilganlar birinchi chiqadi.
        """
        offset = (page - 1) * limit
        q = query.strip().lower()
        in_name = self._lower(Product.name).contains(q, autoescape=True)
        condition = or_(in_name, self._lower(Product.description).contains(q, autoescape=True))
        async with self.session_factory() as session:
            count_stmt = select(func.count(Product.id)).where(condition)
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = (
                select(Product)
                .where(condition)
                .order_by(case((in_name, 0), else_=1), Product.id.desc())
                .offset(offset)
                .limit(limit)
            )
            res = await session.execute(stmt)
            return list(res.scalars().all()), total

    # --- Cart ---
    async def add_to_cart(self, user_id: int, product_id: int, quantity: int = 1) -> Cart:
        async with self.session_factory() as session:
            stmt = select(Cart).where(Cart.user_id == user_id, Cart.product_id == product_id)
            res = await session.execute(stmt)
            cart_item = res.scalar_one_or_none()

            if cart_item:
                cart_item.quantity += quantity
            else:
                cart_item = Cart(user_id=user_id, product_id=product_id, quantity=quantity)
                session.add(cart_item)

            await session.commit()
            await session.refresh(cart_item)
            return cart_item

    async def get_cart_items(self, user_id: int) -> List[Dict[str, Any]]:
        async with self.session_factory() as session:
            stmt = (
                select(Cart)
                .options(selectinload(Cart.product))
                .where(Cart.user_id == user_id)
                .order_by(Cart.id.asc())
            )
            res = await session.execute(stmt)
            cart_rows = res.scalars().all()

            results = []
            for item in cart_rows:
                results.append({
                    "cart_id": item.id,
                    "product_id": item.product_id,
                    "product_name": item.product.name if item.product else "Noma'lum tovar",
                    "price": item.product.price if item.product else "Kelishilgan holda",
                    "quantity": item.quantity,
                    "image_url": item.product.image_url if item.product else None,
                })
            return results

    async def update_cart_quantity(self, cart_id: int, quantity: int) -> bool:
        async with self.session_factory() as session:
            if quantity <= 0:
                stmt = delete(Cart).where(Cart.id == cart_id)
                await session.execute(stmt)
            else:
                stmt = update(Cart).where(Cart.id == cart_id).values(quantity=quantity)
                await session.execute(stmt)
            await session.commit()
            return True

    async def remove_from_cart(self, cart_id: int) -> bool:
        async with self.session_factory() as session:
            stmt = delete(Cart).where(Cart.id == cart_id)
            await session.execute(stmt)
            await session.commit()
            return True

    async def clear_cart(self, user_id: int) -> bool:
        async with self.session_factory() as session:
            stmt = delete(Cart).where(Cart.user_id == user_id)
            await session.execute(stmt)
            await session.commit()
            return True

    # --- Orders ---
    async def create_order(
        self, user_id: int, total_price: str, items: List[Dict[str, Any]]
    ) -> Order:
        async with self.session_factory() as session:
            order = Order(
                user_id=user_id,
                total_price=total_price,
                status="Yangi",
            )
            session.add(order)
            await session.flush()

            for itm in items:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=itm["product_id"],
                    product_name=itm["product_name"],
                    quantity=itm["quantity"],
                    price=itm["price"],
                )
                session.add(order_item)

            await session.commit()
            await session.refresh(order)
            return order

    # --- Admin CRUD Operations ---
    async def delete_brand(self, brand_id: int) -> bool:
        async with self.session_factory() as session:
            stmt = delete(Brand).where(Brand.id == brand_id)
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    async def delete_category(self, category_id: int) -> bool:
        async with self.session_factory() as session:
            stmt = delete(Category).where(Category.id == category_id)
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    async def delete_product(self, product_id: int) -> bool:
        async with self.session_factory() as session:
            stmt = delete(Product).where(Product.id == product_id)
            res = await session.execute(stmt)
            await session.commit()
            return res.rowcount > 0

    @staticmethod
    def _not_from_channel(url_prefix: str):
        return or_(Product.product_url.is_(None), ~Product.product_url.startswith(url_prefix, autoescape=True))

    async def count_products_not_from(self, url_prefix: str) -> int:
        """Manbasi url_prefix bo'lmagan (masalan, kanaldan kelmagan eski) tovarlar soni."""
        async with self.session_factory() as session:
            stmt = select(func.count(Product.id)).where(self._not_from_channel(url_prefix))
            return (await session.execute(stmt)).scalar() or 0

    async def delete_products_not_from(self, url_prefix: str) -> Tuple[List[int], int]:
        """Kanaldan kelmagan tovarlarni o'chirish; shular tufayli bo'sh qolgan brendlar ham o'chiriladi.

        Savatchadagi yozuvlar CASCADE bilan o'chadi, buyurtmalar tarixi (order_items) saqlanadi.
        Qaytaradi: (o'chirilgan tovar ID'lari, o'chirilgan brendlar soni).
        """
        async with self.session_factory() as session:
            rows = (await session.execute(
                select(Product.id, Product.brand_id).where(self._not_from_channel(url_prefix))
            )).all()
            product_ids = [r[0] for r in rows]
            brand_ids = {r[1] for r in rows if r[1] is not None}
            if not product_ids:
                return [], 0

            await session.execute(delete(Product).where(Product.id.in_(product_ids)))

            removed_brands = 0
            for brand_id in brand_ids:
                has_products = (await session.execute(
                    select(func.count(Product.id)).where(Product.brand_id == brand_id)
                )).scalar()
                has_categories = (await session.execute(
                    select(func.count(Category.id)).where(Category.brand_id == brand_id)
                )).scalar()
                if not has_products and not has_categories:
                    await session.execute(delete(Brand).where(Brand.id == brand_id))
                    removed_brands += 1

            await session.commit()
            return product_ids, removed_brands

    async def update_product_fields(self, product_id: int, **kwargs) -> Optional[Product]:
        async with self.session_factory() as session:
            stmt = select(Product).where(Product.id == product_id)
            res = await session.execute(stmt)
            prod = res.scalar_one_or_none()
            if not prod:
                return None

            for key, val in kwargs.items():
                if hasattr(prod, key):
                    setattr(prod, key, val)

            await session.commit()
        # Brend va kategoriya bilan qayta yuklash (sessiyadan tashqarida ishlatish uchun)
        return await self.get_product_by_id(product_id)

    async def get_stats(self) -> Dict[str, int]:
        async with self.session_factory() as session:
            users_c = (await session.execute(select(func.count(User.id)))).scalar() or 0
            prods_c = (await session.execute(select(func.count(Product.id)))).scalar() or 0
            cats_c = (await session.execute(select(func.count(Category.id)))).scalar() or 0
            brands_c = (await session.execute(select(func.count(Brand.id)))).scalar() or 0
            orders_c = (await session.execute(select(func.count(Order.id)))).scalar() or 0
            return {
                "users": users_c,
                "products": prods_c,
                "categories": cats_c,
                "brands": brands_c,
                "orders": orders_c,
            }

