"""
Клавиатуры для ученика.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List


def get_student_main_menu() -> InlineKeyboardMarkup:
    """Главное меню ученика (инлайн)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎴 Мой табель", callback_data="menu:card"),
        InlineKeyboardButton(text="📅 Мероприятия", callback_data="menu:events"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Объявления", callback_data="menu:announcements"),
        InlineKeyboardButton(text="❓ Задать вопрос", callback_data="menu:question"),
    )
    builder.row(
        InlineKeyboardButton(text="📌 Мои записи", callback_data="menu:my_events"),
    )
    return builder.as_markup()


def get_events_keyboard(events: List[dict]) -> InlineKeyboardMarkup:
    """Список активных мероприятий."""
    builder = InlineKeyboardBuilder()
    for event in events:
        builder.row(
            InlineKeyboardButton(
                text=f"📅 {event['title']} — {event['date']}",
                callback_data=f"event_view:{event['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:back_student"))
    return builder.as_markup()


def get_event_action_keyboard(event_id: int, is_registered: bool, is_full: bool) -> InlineKeyboardMarkup:
    """Кнопки записи/отмены записи на мероприятие."""
    builder = InlineKeyboardBuilder()
    if is_registered:
        builder.row(InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"event_cancel:{event_id}"))
    elif is_full:
        builder.row(InlineKeyboardButton(text="🔒 Мест от вашего класса нет", callback_data=f"event_full:{event_id}"))
    else:
        builder.row(InlineKeyboardButton(text="✅ Записаться", callback_data=f"event_register:{event_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_events"))
    return builder.as_markup()


def get_cancel_registration_keyboard(event_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"event_cancel_confirm:{event_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"event_view:{event_id}"),
    )
    return builder.as_markup()


def get_my_events_keyboard(events: List[dict]) -> InlineKeyboardMarkup:
    """Список мероприятий, на которые записан ученик."""
    builder = InlineKeyboardBuilder()
    for event in events:
        builder.row(
            InlineKeyboardButton(
                text=f"📅 {event['title']} — {event['date']}",
                callback_data=f"event_view:{event['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:back_student"))
    return builder.as_markup()


def get_question_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="question_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="question_cancel"),
    )
    return builder.as_markup()
