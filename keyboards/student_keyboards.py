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
    builder.row(
        InlineKeyboardButton(text="💬 Анонимная поддержка", callback_data="menu:support"),
    )
    return builder.as_markup()


def get_support_chat_keyboard(is_anonymous: bool) -> InlineKeyboardMarkup:
    """Клавиатура внутри активного чата поддержки (для ученика)."""
    builder = InlineKeyboardBuilder()
    if is_anonymous:
        builder.row(
            InlineKeyboardButton(text="👤 Открыть личность", callback_data="support:reveal"),
        )
    builder.row(
        InlineKeyboardButton(text="🚪 Завершить чат", callback_data="support:close"),
        InlineKeyboardButton(text="◀️ В главное меню", callback_data="support:menu"),
    )
    return builder.as_markup()


def get_support_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия в чате (раскрытие/завершение)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"support:confirm_{action}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="support:cancel_action"),
    )
    return builder.as_markup()


def get_support_open_keyboard(has_active_chat: bool) -> InlineKeyboardMarkup:
    """Меню точки входа в поддержку."""
    builder = InlineKeyboardBuilder()
    if has_active_chat:
        builder.row(
            InlineKeyboardButton(text="💬 Продолжить чат", callback_data="support:open"),
        )
    else:
        builder.row(
            InlineKeyboardButton(text="💬 Открыть анонимный чат", callback_data="support:create"),
        )
    builder.row(
        InlineKeyboardButton(text="📋 История чатов", callback_data="support:history"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:back_student"),
    )
    return builder.as_markup()


def get_support_history_keyboard(chats: List[dict]) -> InlineKeyboardMarkup:
    """Список завершённых чатов студента."""
    builder = InlineKeyboardBuilder()
    for chat in chats:
        label = f"Чат #{chat['id']} — {chat['created_at'][:10]}"
        builder.row(
            InlineKeyboardButton(text=label, callback_data=f"support:view_history:{chat['id']}")
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:support"))
    return builder.as_markup()


def get_support_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Назад» в поддержку из уведомления об ответе."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Открыть чат", callback_data="menu:support"))
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
