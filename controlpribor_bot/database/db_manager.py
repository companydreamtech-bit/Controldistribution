from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import event, select, update, delete, func, text, or_
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
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine.sync_engine, "connect", self._enable_sqlite_fk)

    @staticmethod
    def _enable_sqlite_fk(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

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

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        async with self.session_factory() as session:
            stmt = select(User).where(User.telegram_id == telegram_id)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    # --- Brands ---
    async def find_brand(self, name: str, slug: str, exclude_id: Optional[int] = None) -> Optional[Brand]:
        """Nomi (katta-kichik harfsiz) yoki slug'i mos keladigan brendni topish."""
        async with self.session_factory() as session:
            stmt = select(Brand).where(or_(func.lower(Brand.name) == name.lower(), Brand.slug == slug))
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
            stmt = select(Category).where(func.lower(Category.name) == name.lower())
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
            stmt = select(Product).where(func.lower(Product.name) == name.lower()).limit(1)
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
        offset = (page - 1) * limit
        search_pattern = f"%{query.strip()}%"
        async with self.session_factory() as session:
            count_stmt = select(func.count(Product.id)).where(Product.name.ilike(search_pattern))
            total = (await session.execute(count_stmt)).scalar() or 0

            stmt = (
                select(Product)
                .where(Product.name.ilike(search_pattern))
                .order_by(Product.id.desc())
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

