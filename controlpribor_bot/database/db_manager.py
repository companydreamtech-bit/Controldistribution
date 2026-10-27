from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, update, delete, func, text
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


class DatabaseManager:
    def __init__(self, db_url: str = "sqlite+aiosqlite:///database.db"):
        self.engine = create_async_engine(db_url, echo=False)
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

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
    async def add_brand(self, name: str, slug: str) -> Brand:
        async with self.session_factory() as session:
            stmt = select(Brand).where(Brand.name == name)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return existing

            brand = Brand(name=name, slug=slug)
            session.add(brand)
            await session.commit()
            await session.refresh(brand)
            return brand

    async def get_brands(self) -> List[Brand]:
        async with self.session_factory() as session:
            stmt = select(Brand).order_by(Brand.name.asc())
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def get_brand_by_id(self, brand_id: int) -> Optional[Brand]:
        async with self.session_factory() as session:
            stmt = select(Brand).where(Brand.id == brand_id)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

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

    async def add_category(self, name: str, brand_id: Optional[int] = None) -> Category:
        async with self.session_factory() as session:
            stmt = select(Category).where(Category.name == name)
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if existing:
                return existing

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

    async def get_all_categories(self, limit: int = 100) -> List[Category]:
        async with self.session_factory() as session:
            stmt = select(Category).order_by(Category.id.asc()).limit(limit)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def get_category_by_id(self, category_id: int) -> Optional[Category]:
        async with self.session_factory() as session:
            stmt = select(Category).where(Category.id == category_id)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

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
            await session.refresh(prod)
            return prod

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

