import html
from typing import Optional

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from controlpribor_bot.config import Config
from controlpribor_bot.database.db_manager import DatabaseManager
from controlpribor_bot.keyboards.default_kb import get_main_menu_kb, get_contact_kb

start_router = Router(name="start_router")


NO_PHONE = "Ko'rsatilmagan"


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """Telefon raqamini "+998..." ko'rinishiga keltirish; 9 tadan kam raqam bo'lsa None."""
    digits = "".join(filter(str.isdigit, raw or ""))
    if len(digits) < 9:
        return None
    return "+" + digits


def has_phone(user) -> bool:
    return bool(user and user.phone_number and user.phone_number != NO_PHONE)


async def save_registration(db: DatabaseManager, telegram_id: int, full_name: str, phone: str) -> None:
    """Yangi foydalanuvchini yaratish yoki telefonsiz yaratilgan (savatchadan kelgan) yozuvga raqamni yozish."""
    _, created = await db.get_or_create_user(telegram_id=telegram_id, full_name=full_name, phone_number=phone)
    if not created:
        await db.update_user_phone(telegram_id, phone)


class RegistrationStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()


@start_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user:
        await state.clear()
        is_admin = config.is_admin(message.from_user.id)
        text = (
            f"👋 <b>Assalomu alaykum, {html.escape(user.full_name)}!</b>\n\n"
            f"⚡️ <b>«ASF Distribution»</b> rasmiy savdo botiga xush kelibsiz!\n\n"
            f"🏭 Biz O'zbekistonda sanoat elektrotexnikasi, KIPiA, avtomatika va o'lchov asboblarini ishonchli yetkazib beruvchimiz.\n\n"
            f"✨ <b>Siz uchun mavjud imkoniyatlar:</b>\n"
            f"▫️ <b>🏷 Brendlar</b> — Dunyoning yetakchi brendlari bo'yicha saralangan katalog\n"
            f"▫️ <b>📁 Barcha kategoriyalar</b> — AKFIX, CHINT, UZKABEL, Metall shitlar va boshqalar\n"
            f"▫️ <b>🔍 Tovar qidirish</b> — Model yoki kalit so'z orqali bir lahzada topish\n"
            f"▫️ <b>🛒 Savatcha</b> — Xaridlarni qulay jamlash va guruh orqali buyurtma berish\n"
            f"▫️ <b>📞 Bog'lanish</b> — Mutaxassis konsultatsiyasi va texnik yordam\n\n"
            f"👇 <i>Davom etish uchun quyidagi menyudan kerakli bo'limni tanlang:</i>"
        )
        await message.answer(
            text,
            reply_markup=get_main_menu_kb(is_admin=is_admin),
            parse_mode="HTML",
        )
    else:
        await state.set_state(RegistrationStates.waiting_for_name)
        text = (
            f"👋 <b>Assalomu alaykum!</b>\n\n"
            f"⚡️ <b>«ASF Distribution»</b> rasmiy savdo botiga xush kelibsiz!\n\n"
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
        f"Ajoyib, <b>{html.escape(name)}</b>! 🤝\n\n"
        f"Endi buyurtmalarni tasdiqlash va hisob-faktura uchun telefon raqamingizni yuboring.\n\n"
        f"👇 Pastdagi <b>«📱 Telefon raqamni yuborish»</b> tugmasini bosing yoki raqamingizni yozing:"
    )
    await message.answer(
        text,
        reply_markup=get_contact_kb(),
        parse_mode="HTML",
    )


@start_router.message(RegistrationStates.waiting_for_phone, F.contact)
async def process_phone_contact(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    phone = normalize_phone(message.contact.phone_number)

    data = await state.get_data()
    full_name = data.get("full_name", message.from_user.full_name or "Mijoz")

    await save_registration(db, message.from_user.id, full_name, phone)
    await state.clear()

    text = (
        f"🎉 <b>Tabriklaymiz, muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n\n"
        f"Hurmatli <b>{html.escape(full_name)}</b>, siz uchun katalog va buyurtma xizmatlari to'liq ochildi.\n\n"
        f"🛒 Kerakli uskuna va asboblarni tanlash uchun quyidagi menyudan foydalaning:"
    )
    await message.answer(
        text,
        reply_markup=get_main_menu_kb(is_admin=config.is_admin(message.from_user.id)),
        parse_mode="HTML",
    )


@start_router.message(RegistrationStates.waiting_for_phone, F.text)
async def process_phone_text(message: Message, state: FSMContext, db: DatabaseManager, config: Config):
    phone = normalize_phone(message.text)
    if not phone:
        await message.answer(
            "⚠️ <b>Iltimos, telefon raqamingizni to'g'ri formatda kiriting:</b>\n"
            "<i>(Masalan: +998901234567)</i> yoki pastdagi tugmani bosing:",
            reply_markup=get_contact_kb(),
            parse_mode="HTML",
        )
        return

    data = await state.get_data()
    full_name = data.get("full_name", message.from_user.full_name or "Mijoz")

    await save_registration(db, message.from_user.id, full_name, phone)
    await state.clear()

    text = (
        f"🎉 <b>Tabriklaymiz, muvaffaqiyatli ro'yxatdan o'tdingiz!</b>\n\n"
        f"Hurmatli <b>{html.escape(full_name)}</b>, siz uchun katalog va buyurtma xizmatlari to'liq ochildi.\n\n"
        f"🛒 Kerakli uskuna va asboblarni tanlash uchun quyidagi menyudan foydalaning:"
    )
    await message.answer(
        text,
        reply_markup=get_main_menu_kb(is_admin=config.is_admin(message.from_user.id)),
        parse_mode="HTML",
    )
