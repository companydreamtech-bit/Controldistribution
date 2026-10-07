import os
import sys
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

# .env faylini qidirib yuklash (joriy papka yoki ota papkadan)
env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)



@dataclass
class Config:
    BOT_TOKEN: str
    ORDER_GROUP_ID: int
    DB_NAME: str = "database.db"
    BASE_URL: str = "https://controlpribor.uz"

    @property
    def bot_token(self) -> str:
        return self.BOT_TOKEN

    @property
    def order_group_id(self) -> int:
        return self.ORDER_GROUP_ID

    @property
    def base_url(self) -> str:
        return self.BASE_URL

    @property
    def db_name(self) -> str:
        return self.DB_NAME

    @property
    def db_path(self) -> str:
        # DB_PATH env o'zgaruvchisi berilgan bo'lsa (masalan Railway volume: /data/database.db)
        env_db_path = os.getenv("DB_PATH")
        if env_db_path:
            return env_db_path
        # Baza faylini loyiha papkasida saqlash
        base_dir = Path(__file__).resolve().parent
        return str(base_dir / self.DB_NAME)

    @classmethod
    def load(cls) -> "Config":
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            raise ValueError("BOT_TOKEN muhit o'zgaruvchisi topilmadi! Iltimos, .env faylini to'ldiring.")

        order_group_id_raw = os.getenv("ORDER_GROUP_ID", "0")
        try:
            order_group_id = int(order_group_id_raw)
        except ValueError:
            order_group_id = 0

        db_name = os.getenv("DB_NAME", "database.db")
        base_url = os.getenv("BASE_URL", "https://controlpribor.uz")

        return cls(
            BOT_TOKEN=bot_token,
            ORDER_GROUP_ID=order_group_id,
            DB_NAME=db_name,
            BASE_URL=base_url,
        )

