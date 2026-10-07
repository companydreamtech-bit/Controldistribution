from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.keyboards.default_kb import get_main_menu_kb, get_contact_kb

start_router = Router(name="start_router")


class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()


@start_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: DatabaseManager):
    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user:
        await state.clear()
        text = (
            f"👋 <b>Assalomu alaykum, {user.full_name}!</b>\n\n"
            f"⚡️ <b>«CONTROL PRIBOR»</b> rasmiy savdo botiga xush kelibsiz!\n\n"
            f"🏭 Biz O'zbekistonda sanoat elektrotexnikasi, KIPiA, avtomatika va o'lchov asboblarini ishonchli yetkazib beruvchimiz.\n\n"
            f"✨ <b>Siz uchun mavjud imkoniyatlar:</b>\n"
            f"▫️ <b>🏷 Brendlar</b> — Dunyoning yetakchi brendlari bo'yicha saralangan katalog\n"
            f"▫️ <b>📁 Barcha kategoriyalar</b> — KIPiA, pirometrlar, multimetrlar, relelar\n"
            f"▫️ <b>🔍 Tovar qidirish</b> — Model yoki kalit so'z orqali bir lahzada topish\n"
            f"▫️ <b>🛒 Savatcha</b> — Xaridlarni qulay jamlash va guruh orqali buyurtma berish\n"
            f"▫️ <b>📞 Bog'lanish</b> — Mutaxassis konsultatsiyasi va texnik yordam\n\n"
            f"👇 <i>Davom etish uchun quyidagi menyudan kerakli bo'limni tanlang:</i>"
        )
        await message.answer(
            text,
            reply_markup=get_main_menu_kb(),
            parse_mode="HTML",
        )
    else:
        await state.set_state(RegistrationStates.waiting_for_name)
        text = (
            f"👋 <b>Assalomu alaykum!</b>\n\n"
            f"⚡️ <b>«CONTROL PRIBOR»</b> rasmiy savdo botiga xush kelibsiz!\n\n"
            f"🏭 Bu yerda siz sanoat elektrotexnikasi, KIPiA, o'lchov asboblari va materiallarni to'g'ridan-to'g'ri birinchi qo'ldan xarid qilishingiz mumkin.\n\n"
            f"🔐 <i>Buyurtmalaringizni tezkor rasmiylashtirish va do'konimiz imkoniyatlaridan to'liq foydalanish uchun, iltimos, ro'yxatdan o'ting.</i>\n\n"
            f"👤 <b>Ism va familiyangizni kiriting:</b>\n"
            f"<i>(Masalan: Sardor Karimov)</i>"
        )
        await message.answer(
            text,
            parse_mode="HTML",
        )


@start_router.message(RegistrationStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip() if message.text else ""
    if len(name) < 3:
        await message.answer(
            "⚠️ <b>Iltimos, ism va familiyangizni to'liq kiriting:</b>\n"
            "<i>(Masalan: Alisher Karimov)</i>",
            parse_mode="HTML",
        )
        return

    await state.update_data(full_name=name)
    await state.set_state(RegistrationStates.waiting_for_phone)
    text = (
        f"Ajoyib, <b>{name}</b>! 🤝\n\n"
        f"Endi buyurtmalarni tasdiqlash va hisob-faktura uchun telefon raqamingizni yuboring.\n\n"
        f"👇 Pastdagi <b>«📱 Telefon raqamni yuborish»</b> tugmasini bosing yoki raqamingizni yozing:"
    )
    await message.answer(
        text,
        reply_markup=get_contact_kb(),
        parse_mode="HTML",
    )


@start_router.message(RegistrationStates.waiting_for_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext, db: DatabaseManager):
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone

    data = await state.get_data()
    full_name = data.get("full_name", message.from_user.full_name or "Mijoz")

    await db.get_or_create_user(
        telegram_id=message.from_user.id,
        full_name=full_name,
        phone_number=phone,
    )
    await state.clear()

    text = (
        f"🎉 <b>Tabriklaymiz, muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n\n"
        f"Hurmatli <b>{full_name}</b>, siz uchun katalog va buyurtma xizmatlari to'liq ochildi.\n\n"
        f"🛒 Kerakli uskuna va asboblarni tanlash uchun quyidagi menyudan foydalaning:"
    )
    await message.answer(
        text,
        reply_markup=get_main_menu_kb(),
        parse_mode="HTML",
    )


@start_router.message(RegistrationStates.waiting_for_phone, F.text)
async def process_phone_text(message: Message, state: FSMContext, db: DatabaseManager):
    phone = message.text.strip()
    cleaned_digits = "".join(filter(str.isdigit, phone))
    if len(cleaned_digits) < 9:
        await message.answer(
            "⚠️ <b>Iltimos, telefon raqamingizni to'g'ri formatda kiriting:</b>\n"
            "<i>(Masalan: +998901234567)</i> yoki pastdagi tugmani bosing:",
            reply_markup=get_contact_kb(),
            parse_mode="HTML",
        )
        return

    if not phone.startswith("+"):
        phone = "+" + cleaned_digits

    data = await state.get_data()
    full_name = data.get("full_name", message.from_user.full_name or "Mijoz")

    await db.get_or_create_user(
        telegram_id=message.from_user.id,
        full_name=full_name,
        phone_number=phone,
    )
    await state.clear()

    text = (
        f"🎉 <b>Tabriklaymiz, muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n\n"
        f"Hurmatli <b>{full_name}</b>, siz uchun katalog va buyurtma xizmatlari to'liq ochildi.\n\n"
        f"🛒 Kerakli uskuna va asboblarni tanlash uchun quyidagi menyudan foydalaning:"
    )
    await message.answer(
        text,
        reply_markup=get_main_menu_kb(),
        parse_mode="HTML",
    )
