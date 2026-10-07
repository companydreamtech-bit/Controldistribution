import asyncio
import logging
import sys
from pathlib import Path

# Loyiha ildiz papkasini sys.path ga qo'shish
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from controlpribor_bot.config import Config
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.handlers.start import start_router
from controlpribor_bot.handlers.catalog import catalog_router
from controlpribor_bot.handlers.search import search_router
from controlpribor_bot.handlers.cart import cart_router
from controlpribor_bot.handlers.other import other_router

# Log sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("controlpribor_bot")


def setup_dispatcher(db: DatabaseManager, config: Config) -> Dispatcher:
    """Dispatcher yaratish va barcha routerlarni ro'yxatga olish."""
    dp = Dispatcher()

    # Dependency injection: barcha handlerlarga db va config ni uzatish
    dp["db"] = db
    dp["config"] = config

    # Routerlarni ulash
    dp.include_router(start_router)
    dp.include_router(catalog_router)
    dp.include_router(search_router)
    dp.include_router(cart_router)
    dp.include_router(other_router)

    return dp


async def main():
    logger.info("Bot ishga tushirilmoqda...")

    # 1. Konfiguratsiyani yuklash
    try:
        config = Config.load()
    except Exception as e:
        logger.error(f"Konfiguratsiya yuklashda xatolik: {e}")
        return

    # 2. Ma'lumotlar bazasini ishga tushirish
    db_target = Path(config.db_path)
    default_db = Path(__file__).resolve().parent / "database.db"
    if str(db_target.resolve()) != str(default_db.resolve()) and not db_target.exists() and default_db.exists():
        import shutil
        db_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(default_db, db_target)
        logger.info(f"Boshlang'ich baza {default_db} dan {db_target} ga nusxalandi.")

    db_url = f"sqlite+aiosqlite:///{config.db_path}"
    db = DatabaseManager(db_url)
    await db.init_db()
    logger.info("Ma'lumotlar bazasi tayyorlandi.")

    # 3. Bot va Dispatcher yaratish
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = setup_dispatcher(db=db, config=config)

    # 4. Pollingni boshlash
    try:
        # Eski keshdagi yangilanishlarni tozalash
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Bot muvaffaqiyatli ishga tushdi va xabarlarni qabul qilmoqda!")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Bot ishlashida xatolik: {e}")
    finally:
        logger.info("Bot to'xtatilmoqda...")
        await db.close()
        await bot.session.close()
        logger.info("Bot to'liq to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot foydalanuvchi tomonidan to'xtatildi.")
