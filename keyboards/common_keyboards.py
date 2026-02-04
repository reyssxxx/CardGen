"""
Клавиатуры для общего функционала (регистрация, помощь)
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_registration_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора роли при регистрации

    Returns:
        Inline клавиатура с кнопками "Я ученик" и "Я учитель"
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="👶 Я ученик", callback_data="register_student")
    )

    builder.row(
        InlineKeyboardButton(text="👨‍🏫 Я учитель", callback_data="register_teacher")
    )

    return builder.as_markup()
