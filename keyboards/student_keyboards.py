"""
Клавиатуры для функционала ученика
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List


def get_student_main_menu() -> ReplyKeyboardMarkup:
    """
    Главное меню ученика (Reply клавиатура)

    Returns:
        Reply клавиатура с основными командами
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="📊 Мои оценки"),
        KeyboardButton(text="🎴 Получить табель")
    )

    builder.row(
        KeyboardButton(text="📈 Статистика"),
        KeyboardButton(text="ℹ️ Помощь")
    )

    return builder.as_markup(resize_keyboard=True)


def get_period_selection_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора периода для просмотра оценок

    Returns:
        Inline клавиатура с периодами
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="За неделю (7 дней)", callback_data="period:7")
    )

    builder.row(
        InlineKeyboardButton(text="За 2 недели (14 дней) ⭐", callback_data="period:14")
    )

    builder.row(
        InlineKeyboardButton(text="За месяц (30 дней)", callback_data="period:30")
    )

    builder.row(
        InlineKeyboardButton(text="За полугодие (90 дней)", callback_data="period:90")
    )

    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_period")
    )

    return builder.as_markup()


def get_subject_filter_keyboard(subjects: List[str]) -> InlineKeyboardMarkup:
    """
    Клавиатура фильтра по предметам

    Args:
        subjects: Список предметов ученика

    Returns:
        Inline клавиатура с предметами
    """
    builder = InlineKeyboardBuilder()

    # Кнопка "Все предметы"
    builder.row(
        InlineKeyboardButton(text="📚 Все предметы", callback_data="subject:all")
    )

    # Кнопки предметов
    for subject in subjects:
        builder.button(
            text=subject,
            callback_data=f"subject:{subject}"
        )

    # 2 предмета в ряд
    builder.adjust(1, *[2] * (len(subjects) // 2 + 1))

    # Кнопка назад
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu")
    )

    return builder.as_markup()
