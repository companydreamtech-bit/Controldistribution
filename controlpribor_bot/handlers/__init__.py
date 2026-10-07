from controlpribor_bot.handlers.start import start_router
from controlpribor_bot.handlers.catalog import catalog_router
from controlpribor_bot.handlers.search import search_router
from controlpribor_bot.handlers.cart import cart_router
from controlpribor_bot.handlers.other import other_router

__all__ = [
    "start_router",
    "catalog_router",
    "search_router",
    "cart_router",
    "other_router",
]
