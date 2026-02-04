"""
Клавиатуры для функционала администратора
"""
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List


def get_admin_main_menu() -> ReplyKeyboardMarkup:
    """
    Главное меню администратора (Reply клавиатура)

    Returns:
        Reply клавиатура с основными командами админа
    """
    builder = ReplyKeyboardBuilder()

    # Основные кнопки
    builder.button(text="📊 Состояние журнала")
    builder.button(text="📢 Массовая рассылка")
    builder.button(text="🔄 Принудительная рассылка")

    # Располагаем по 1 кнопке в ряд для лучшей читаемости
    builder.adjust(1)

    return builder.as_markup(resize_keyboard=True)


def get_admin_send_audience_keyboard(classes: List[str] = None) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора аудитории для массовой рассылки

    Args:
        classes: Список доступных классов (опционально)

    Returns:
        Inline клавиатура с вариантами аудитории
    """
    builder = InlineKeyboardBuilder()

    # Основные аудитории
    builder.row(
        InlineKeyboardButton(
            text="👥 Всем ученикам",
            callback_data="admin_send:all_students"
        )
    )

    builder.row(
        InlineKeyboardButton(
            text="👨‍🏫 Всем учителям",
            callback_data="admin_send:all_teachers"
        )
    )

    # Если переданы классы, добавить кнопки для каждого класса
    if classes:
        for class_name in classes:
            builder.button(
                text=f"📚 Класс {class_name}",
                callback_data=f"admin_send_class:{class_name}"
            )

        # Располагаем классы по 3 в ряд
        builder.adjust(1, 1, 3)

    # Кнопка отмены
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
    )

    return builder.as_markup()


def get_admin_send_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения рассылки

    Returns:
        Inline клавиатура с кнопками подтверждения/отмены
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="admin_send_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
    )

    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """
    Простая клавиатура с кнопкой отмены

    Returns:
        Inline клавиатура только с отменой
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
    )

    return builder.as_markup()
