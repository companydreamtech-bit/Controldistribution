import pytest
from aiogram import Router
from controlpribor_bot.handlers.start import start_router
from controlpribor_bot.handlers.catalog import catalog_router
from controlpribor_bot.handlers.search import search_router
from controlpribor_bot.handlers.cart import cart_router
from controlpribor_bot.handlers.other import other_router

def test_routers_exist():
    assert isinstance(start_router, Router)
    assert isinstance(catalog_router, Router)
    assert isinstance(search_router, Router)
    assert isinstance(cart_router, Router)
    assert isinstance(other_router, Router)

def test_router_handlers_registered():
    assert len(start_router.message.handlers) >= 1
    assert len(catalog_router.message.handlers) >= 1 or len(catalog_router.callback_query.handlers) >= 1
    assert len(search_router.message.handlers) >= 1
    assert len(cart_router.message.handlers) >= 1 or len(cart_router.callback_query.handlers) >= 1
    assert len(other_router.message.handlers) >= 1
