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
        InlineKeyboardButton(text="❓ Вопросы", callback_data="menu:question"),
    )
    return builder.as_markup()


def get_events_keyboard(events: List[dict]) -> InlineKeyboardMarkup:
    """Список активных мероприятий (дней)."""
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


def get_event_sections_keyboard(event_id: int, sections: list, user_sections: list) -> InlineKeyboardMarkup:
    """Список секций дня с отметками записи."""
    builder = InlineKeyboardBuilder()
    for s in sections:
        registered = s["id"] in user_sections
        check = "✅ " if registered else ""
        time_str = f"{s['time']} " if s.get('time') else ""
        label = f"{check}🕐 {time_str}{s['title']}"
        builder.row(InlineKeyboardButton(text=label[:64], callback_data=f"sec_view:{s['id']}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к мероприятиям", callback_data="back_to_events"))
    return builder.as_markup()


def get_section_action_keyboard(section_id: int, event_id: int,
                                is_registered: bool, is_full: bool) -> InlineKeyboardMarkup:
    """Кнопки записи/отмены записи на секцию."""
    builder = InlineKeyboardBuilder()
    if is_registered:
        builder.row(InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"sec_cancel:{section_id}"))
    elif is_full:
        builder.row(InlineKeyboardButton(text="🔒 Мест нет", callback_data=f"sec_full:{section_id}"))
    else:
        builder.row(InlineKeyboardButton(text="✅ Записаться", callback_data=f"sec_register:{section_id}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад к секциям", callback_data=f"event_view:{event_id}"))
    return builder.as_markup()


def get_cancel_section_keyboard(section_id: int, event_id: int) -> InlineKeyboardMarkup:
    """Подтверждение отмены записи на секцию."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"sec_cancel_confirm:{section_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"sec_view:{section_id}"),
    )
    return builder.as_markup()


# Обратная совместимость — старые мероприятия без секций
def get_event_action_keyboard(event_id: int, is_registered: bool, is_full: bool) -> InlineKeyboardMarkup:
    """Кнопки записи на старые мероприятия (без секций)."""
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


# ── Вопросы ──────────────────────────────────────────────────────────────────

def get_questions_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела вопросов: задать новый или посмотреть свои."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Задать вопрос", callback_data="q:new"))
    builder.row(InlineKeyboardButton(text="📋 Мои вопросы", callback_data="q:my"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:back_student"))
    return builder.as_markup()


def get_question_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="question_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="question_cancel"),
    )
    return builder.as_markup()


def get_my_questions_keyboard(questions: List[dict]) -> InlineKeyboardMarkup:
    """Список вопросов ученика."""
    from datetime import datetime
    builder = InlineKeyboardBuilder()
    for q in questions:
        status = "✅" if q["answered"] else "⏳"
        try:
            dt = datetime.fromisoformat(q["created_at"]).strftime("%d.%m")
        except (ValueError, TypeError):
            dt = ""
        short = q["text"][:30] + ("..." if len(q["text"]) > 30 else "")
        label = f"{status} {dt} {short}"
        builder.row(
            InlineKeyboardButton(
                text=label[:64],
                callback_data=f"my_q_view:{q['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:question"))
    return builder.as_markup()


def get_question_detail_keyboard() -> InlineKeyboardMarkup:
    """Кнопка назад из просмотра вопроса."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="q:my"))
    return builder.as_markup()


# ── Объявления ────────────────────────────────────────────────────────────────

def get_announcement_nav_keyboard(index: int, total: int) -> InlineKeyboardMarkup:
    """Навигация по объявлениям: prev / счётчик / next + назад."""
    builder = InlineKeyboardBuilder()
    nav = []
    if index > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"ann:{index - 1}"))
    nav.append(InlineKeyboardButton(text=f"{index + 1}/{total}", callback_data="ann_noop"))
    if index < total - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"ann:{index + 1}"))
    builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🏠 В меню", callback_data="menu:back_student"))
    return builder.as_markup()
