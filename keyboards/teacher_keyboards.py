"""
Клавиатуры для учителя.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List


def get_teacher_main_menu() -> InlineKeyboardMarkup:
    """Главное меню учителя (инлайн)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📢 Объявление классу", callback_data="teacher:announce"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Мои классы", callback_data="teacher:my_classes"),
        InlineKeyboardButton(text="📋 История рассылок", callback_data="teacher:history"),
    )
    return builder.as_markup()


def get_teacher_class_keyboard(classes: List[str], callback_prefix: str) -> InlineKeyboardMarkup:
    """Список классов учителя для выбора."""
    builder = InlineKeyboardBuilder()
    for cls in classes:
        builder.button(text=cls, callback_data=f"{callback_prefix}:{cls}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:back_teacher"))
    return builder.as_markup()


def get_teacher_announcement_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="teacher_announce_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="menu:back_teacher"),
    )
    return builder.as_markup()
