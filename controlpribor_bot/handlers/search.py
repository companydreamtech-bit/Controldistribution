import math
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.keyboards.inline_kb import get_products_list_kb

search_router = Router(name="search_router")
PER_PAGE = 6


class SearchStates(StatesGroup):
    waiting_for_query = State()


@search_router.message(F.text == "🔍 Tovar qidirish")
async def prompt_search(message: Message, state: FSMContext):
    await state.set_state(SearchStates.waiting_for_query)
    await message.answer(
        "🔍 <b>Tezkor tovar qidirish:</b>\n\n"
        "Qidirayotgan tovar modeli yoki nomini yozib yuboring:\n"
        "<i>(Masalan: 303, MY-64, klesh, rele, pirometr, akfix)</i>",
        parse_mode="HTML",
    )


@search_router.message(SearchStates.waiting_for_query, F.text)
async def perform_state_search(message: Message, state: FSMContext, db: DatabaseManager):
    query = message.text.strip()
    await state.update_data(last_search_query=query)
    await execute_search(message, query, page=1, db=db)


# Foydalanuvchi qidiruv tugmasini bosmasdan to'g'ridan-to'g'ri matn yozsa ham qidirish (lekin bosh menyu buyruqlari bo'lmasa)
@search_router.message(
    F.text
    & ~F.text.startswith("/")
    & ~F.text.in_([
        "🏷 Brendlar",
        "📁 Barcha kategoriyalar",
        "🔍 Tovar qidirish",
        "🛒 Savatcha",
        "📞 Bog'lanish / Menejer",
        "📱 Telefon raqamni yuborish",
    ])
)
async def direct_text_search(message: Message, state: FSMContext, db: DatabaseManager):
    query = message.text.strip()
    if len(query) < 2:
        return
    await state.update_data(last_search_query=query)
    await execute_search(message, query, page=1, db=db)


async def execute_search(message: Message, query: str, page: int, db: DatabaseManager):
    products, total = await db.search_products(query=query, page=page, limit=PER_PAGE)
    total_pages = max(1, math.ceil(total / PER_PAGE))

    if not products:
        await message.answer(
            f"🔍 '{query}' so'rovi bo'yicha hech qanday mahsulot topilmadi.\n\n"
            "Iltimos, model yoki nomini to'g'ri yozganingizni tekshirib ko'ring yoki boshqa so'z bilan qidiring."
        )
        return

    kb = get_products_list_kb(
        products=products,
        page=page,
        total_pages=total_pages,
        category_id=None,
        brand_id=None,
        search_query=query,
    )
    await message.answer(
        f"🔍 <b>'{query}'</b> bo'yicha topildi ({total} ta mahsulot):\n\nKerakli mahsulotni tanlang:",
        reply_markup=kb,
        parse_mode="HTML",
    )


@search_router.callback_query(F.data.startswith("prods_search_page_"))
async def handle_search_pagination(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    await callback.answer()
    page = int(callback.data.split("_")[-1])
    data = await state.get_data()
    query = data.get("last_search_query", "")

    if not query:
        await callback.message.answer("Qidiruv so'rovi eskirgan. Qaytadan qidiring.")
        return

    products, total = await db.search_products(query=query, page=page, limit=PER_PAGE)
    total_pages = max(1, math.ceil(total / PER_PAGE))

    kb = get_products_list_kb(
        products=products,
        page=page,
        total_pages=total_pages,
        category_id=None,
        brand_id=None,
        search_query=query,
    )
    await callback.message.edit_text(
        f"🔍 <b>'{query}'</b> bo'yicha topildi ({total} ta mahsulot):",
        reply_markup=kb,
        parse_mode="HTML",
    )


@search_router.callback_query(F.data == "back_to_search")
async def back_to_search_results(callback: CallbackQuery, state: FSMContext, db: DatabaseManager):
    await callback.answer()
    data = await state.get_data()
    query = data.get("last_search_query", "")
    if query:
        products, total = await db.search_products(query=query, page=1, limit=PER_PAGE)
        total_pages = max(1, math.ceil(total / PER_PAGE))
        kb = get_products_list_kb(products, page=1, total_pages=total_pages)
        await callback.message.delete()
        await callback.message.answer(
            f"🔍 <b>'{query}'</b> natijalari:",
            reply_markup=kb,
            parse_mode="HTML",
        )
    else:
        await callback.message.delete()
        await callback.message.answer("Qidiruv natijalari eskirgan. Yangi so'rov yuboring.")
