import pytest
from aiogram import Bot, Dispatcher
from controlpribor_bot.bot import setup_dispatcher
from controlpribor_bot.config import Config
from controlpribor_bot.database.db_manager import DatabaseManager

def test_setup_dispatcher(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST_TOKEN")
    monkeypatch.setenv("ORDER_GROUP_ID", "-100123")
    config = Config.load()
    db = DatabaseManager(f"sqlite+aiosqlite:///test_bot.db")
    
    dp = setup_dispatcher(db=db, config=config)
    assert isinstance(dp, Dispatcher)
    assert "db" in dp.workflow_data
    assert "config" in dp.workflow_data
    # Check that routers are included
    assert len(dp.sub_routers) >= 5
