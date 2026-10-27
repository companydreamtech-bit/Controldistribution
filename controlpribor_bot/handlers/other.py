from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

other_router = Router(name="other_router")


@other_router.message(F.text == "📞 Bog'lanish / Menejer")
@other_router.message(Command("help"))
async def show_contacts(message: Message):
    text = (
        "🏢 <b>'ASF Distribution' MChJ</b>\n"
        "<i>Sanoat elektrotexnikasi, avtomatika va KIPiA uskunalari bo'yicha ishonchli hamkoringiz!</i>\n\n"
        "📞 <b>Telefonlar:</b>\n"
        "• +998 (71) 200-00-00\n"
        "• +998 (90) 123-45-67 (Menejer)\n\n"
        "💬 <b>Telegram:</b> @controlpribor_admin\n"
        "📢 <b>Rasmiy kanal:</b> @controlpribor\n\n"
        "📍 <b>Manzil:</b> Toshkent sh., Olmazor tumani, Usta Shirin bozori, 1-qator\n"
        "⏰ <b>Ish vaqti:</b> 09:00 - 18:00 (Dushanba - Shanba)\n\n"
        "Savollaringiz bo'lsa, mutaxassislarimizga murojaat qiling!"
    )
    await message.answer(text, parse_mode="HTML")
