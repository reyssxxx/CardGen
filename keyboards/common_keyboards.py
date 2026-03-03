"""
Клавиатуры для общего функционала (регистрация)
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List


def get_registration_keyboard() -> InlineKeyboardMarkup:
    """Выбор роли при регистрации (только для тех, кто не в списках)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👨‍🎓 Я ученик", callback_data="register_student"),
        InlineKeyboardButton(text="👩‍🏫 Я учитель", callback_data="register_teacher_request"),
    )
    return builder.as_markup()


def get_class_selection_keyboard(classes: List[str]) -> InlineKeyboardMarkup:
    """Выбор класса при регистрации ученика."""
    builder = InlineKeyboardBuilder()
    for cls in classes:
        builder.button(text=cls, callback_data=f"reg_class:{cls}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="reg_cancel"))
    return builder.as_markup()


def get_name_selection_keyboard(names: List[str]) -> InlineKeyboardMarkup:
    """Выбор имени из списка класса при регистрации."""
    builder = InlineKeyboardBuilder()
    for name in names:
        builder.button(text=name, callback_data=f"reg_name:{name}")
    builder.adjust(2)
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="reg_back_class"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="reg_cancel"),
    )
    return builder.as_markup()


def get_confirm_registration_keyboard() -> InlineKeyboardMarkup:
    """Подтверждение выбранного имени."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, это я", callback_data="reg_confirm"),
        InlineKeyboardButton(text="◀️ Нет, назад", callback_data="reg_back_name"),
    )
    return builder.as_markup()


def get_cancel_keyboard(callback: str = "cancel") -> InlineKeyboardMarkup:
    """Клавиатура только с кнопкой Отмена."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data=callback))
    return builder.as_markup()
