from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


def get_main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Asosiy menyu reply klaviaturasi."""
    keyboard = [
        [
            KeyboardButton(text="🏷 Brendlar"),
            KeyboardButton(text="📁 Barcha kategoriyalar"),
        ],
        [
            KeyboardButton(text="🔍 Tovar qidirish"),
            KeyboardButton(text="🛒 Savatcha"),
        ],
        [
            KeyboardButton(text="📞 Bog'lanish / Menejer"),
        ],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="⚙️ Admin panel")])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Kerakli bo'limni tanlang...",
    )


def get_contact_kb() -> ReplyKeyboardMarkup:
    """Telefon raqamni yuborish klaviaturasi."""
    keyboard = [
        [
            KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True),
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Kontaktni ulashish tugmasini bosing...",
    )
