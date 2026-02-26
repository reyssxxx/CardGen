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


def get_event_slots_keyboard(event_id: int, slots: List[str],
                              unavailable_slots: List[str],
                              registered_slots: List[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        if slot in registered_slots:
            label = f"✅ {slot} — ты записан"
            cb = f"event_cancel:{event_id}:{slot}"
        elif slot in unavailable_slots:
            label = f"🔒 {slot} — мест нет"
            cb = f"event_full:{event_id}:{slot}"
        else:
            label = f"🕐 {slot} — есть места"
            cb = f"event_register:{event_id}:{slot}"
        builder.row(InlineKeyboardButton(text=label, callback_data=cb))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_events"))
    return builder.as_markup()


def get_cancel_registration_keyboard(event_id: int, slot: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"event_cancel_confirm:{event_id}:{slot}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"event_view:{event_id}"),
    )
    return builder.as_markup()


def get_question_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="question_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="question_cancel"),
    )
    return builder.as_markup()
