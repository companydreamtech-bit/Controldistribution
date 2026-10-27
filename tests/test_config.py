import os
import pytest
from controlpribor_bot.config import Config

def test_config_loads_defaults(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST_TOKEN")
    monkeypatch.setenv("ORDER_GROUP_ID", "-100123456789")
    monkeypatch.setenv("DB_NAME", "test_database.db")
    
    config = Config.load()
    assert config.BOT_TOKEN == "123456:TEST_TOKEN"
    assert config.ORDER_GROUP_ID == -100123456789
    assert config.DB_NAME == "test_database.db"
    assert config.BASE_URL == "https://controlpribor.uz"

def test_config_missing_bot_token(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        Config.load()

def test_config_admin_ids(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456:TEST_TOKEN")
    monkeypatch.setenv("ADMIN_IDS", "12345, 67890, abc")
    config = Config.load()
    assert config.ADMIN_IDS == [12345, 67890]
    assert config.is_admin(12345) is True
    assert config.is_admin(99999) is False

