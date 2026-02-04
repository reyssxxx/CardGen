"""
Клавиатуры для функционала учителя
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List, Optional


def get_subject_selection_keyboard(subjects: List[str]) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора предмета

    Args:
        subjects: Список предметов учителя

    Returns:
        Inline клавиатура с кнопками предметов
    """
    builder = InlineKeyboardBuilder()

    for subject in subjects:
        builder.button(
            text=subject,
            callback_data=f"subject:{subject}"
        )

    # Располагаем по 2 кнопки в ряд
    builder.adjust(2)

    # Кнопка отмены
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )

    return builder.as_markup()


def get_class_selection_keyboard(classes: List[str],
                                 allow_auto_detect: bool = True) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора класса

    Args:
        classes: Список классов
        allow_auto_detect: Разрешить автоопределение класса из фото

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    # Автоопределение (если разрешено)
    if allow_auto_detect:
        builder.row(
            InlineKeyboardButton(
                text="🤖 Определить автоматически",
                callback_data="class:auto"
            )
        )

    # Кнопки классов
    for class_name in classes:
        builder.button(
            text=class_name,
            callback_data=f"class:{class_name}"
        )

    builder.adjust(3)  # 3 класса в ряд

    # Кнопка отмены
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )

    return builder.as_markup()


def get_grade_edit_keyboard(student_index: int, date_index: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для редактирования оценки

    Args:
        student_index: Индекс ученика
        date_index: Индекс даты (столбца)

    Returns:
        Inline клавиатура с оценками
    """
    builder = InlineKeyboardBuilder()

    # Оценки
    grades = ['5', '4', '3', '2']
    for grade in grades:
        builder.button(
            text=grade,
            callback_data=f"edit_grade:{student_index}:{date_index}:{grade}"
        )

    builder.adjust(4)  # Все оценки в один ряд

    # Специальные оценки
    builder.row(
        InlineKeyboardButton(text="н/н", callback_data=f"edit_grade:{student_index}:{date_index}:н/н"),
        InlineKeyboardButton(text="н", callback_data=f"edit_grade:{student_index}:{date_index}:н"),
        InlineKeyboardButton(text="б", callback_data=f"edit_grade:{student_index}:{date_index}:б"),
    )

    # Удалить оценку
    builder.row(
        InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"edit_grade:{student_index}:{date_index}:delete"
        )
    )

    # Назад
    builder.row(
        InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_review")
    )

    return builder.as_markup()


def get_student_review_keyboard(student_index: int,
                                num_dates: int,
                                is_last_student: bool = False) -> InlineKeyboardMarkup:
    """
    Клавиатура для просмотра/редактирования оценок ученика

    Args:
        student_index: Индекс ученика
        num_dates: Количество дат (столбцов)
        is_last_student: Последний ли это ученик

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    # Кнопки редактирования для каждой даты (колонки)
    if num_dates > 0:
        for date_idx in range(num_dates):
            builder.button(
                text=f"Столбец {date_idx + 1}",
                callback_data=f"review_edit:{student_index}:{date_idx}"
            )

        builder.adjust(min(5, num_dates))  # Максимум 5 кнопок в ряд

    # Навигация
    nav_buttons = []

    if student_index > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="◀️ Предыдущий", callback_data=f"review_student:{student_index - 1}")
        )

    if not is_last_student:
        nav_buttons.append(
            InlineKeyboardButton(text="Следующий ▶️", callback_data=f"review_student:{student_index + 1}")
        )

    if nav_buttons:
        builder.row(*nav_buttons)

    # Все верно для этого ученика
    builder.row(
        InlineKeyboardButton(text="✅ Все верно", callback_data=f"confirm_student:{student_index}")
    )

    return builder.as_markup()


def get_date_review_keyboard(num_dates: int) -> InlineKeyboardMarkup:
    """
    Клавиатура для проверки распознанных дат

    Args:
        num_dates: Количество дат

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    # Кнопки редактирования каждой даты
    for date_idx in range(num_dates):
        builder.button(
            text=f"Дата {date_idx + 1}",
            callback_data=f"edit_date:{date_idx}"
        )

    builder.adjust(min(4, num_dates))

    # Все верно
    builder.row(
        InlineKeyboardButton(text="✅ Все даты верны", callback_data="dates_confirmed")
    )

    # Отмена
    builder.row(
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )

    return builder.as_markup()


def get_final_confirmation_keyboard() -> InlineKeyboardMarkup:
    """
    Финальная клавиатура подтверждения перед сохранением в БД

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Сохранить все оценки", callback_data="save_grades"),
        InlineKeyboardButton(text="✏️ Продолжить редактирование", callback_data="continue_editing")
    )

    builder.row(
        InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_all")
    )

    return builder.as_markup()


def get_teacher_main_menu() -> ReplyKeyboardMarkup:
    """
    Главное меню учителя (Reply клавиатура)

    Returns:
        Reply клавиатура
    """
    builder = ReplyKeyboardBuilder()

    builder.row(
        KeyboardButton(text="📸 Загрузить фото журнала"),
        KeyboardButton(text="✏️ Добавить оценку вручную")
    )

    builder.row(
        KeyboardButton(text="📝 Редактировать оценку"),
        KeyboardButton(text="📊 Статистика класса")
    )

    builder.row(
        KeyboardButton(text="📢 Отправить сообщение классу"),
        KeyboardButton(text="📋 Мои загрузки")
    )

    builder.row(
        KeyboardButton(text="ℹ️ Помощь")
    )

    return builder.as_markup(resize_keyboard=True)


def get_yes_no_keyboard(yes_callback: str = "yes",
                       no_callback: str = "no") -> InlineKeyboardMarkup:
    """
    Простая клавиатура Да/Нет

    Args:
        yes_callback: Callback data для кнопки "Да"
        no_callback: Callback data для кнопки "Нет"

    Returns:
        Inline клавиатура
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=yes_callback),
        InlineKeyboardButton(text="❌ Нет", callback_data=no_callback)
    )

    return builder.as_markup()
