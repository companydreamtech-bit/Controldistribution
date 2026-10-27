from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

other_router = Router(name="other_router")


@other_router.message(F.text == "📞 Bog'lanish / Menejer")
@other_router.message(Command("help"))
async def show_contacts(message: Message):
    # Ma'lumotlar rasmiy kanaldan olingan: https://t.me/asfdistribution
    text = (
        "🏢 <b>ASF Distribution — rasmiy distribyutor</b>\n"
        "<i>AKFIX • CHINT • BAUMANN • PROFMET • NURA • NILSON • UZKABEL • PROCAB</i>\n\n"
        "⚡️ Elektr tovarlari | 🔌 Kabellar | 💡 Yoritish mahsulotlari\n"
        "📦 OPTOM narxlar va doimiy sklad mavjud\n\n"
        "📞 <b>Telefonlar:</b>\n"
        "• +998 50 515 51 11\n"
        "• +998 99 901 59 11\n\n"
        "💬 <b>Telegram:</b> @S_77777_S, @controldistribution\n"
        "📢 <b>Rasmiy kanal:</b> @asfdistribution\n\n"
        "Savollaringiz bo'lsa, mutaxassislarimizga murojaat qiling!"
    )
    await message.answer(text, parse_mode="HTML")
