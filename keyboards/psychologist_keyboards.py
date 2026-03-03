"""
Клавиатуры для психолога.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List


def get_psychologist_main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💬 Активные чаты", callback_data="psych:active"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Завершённые чаты", callback_data="psych:closed"),
    )
    return builder.as_markup()


def _chat_label(chat: dict) -> str:
    """Формирует название чата для списка."""
    if chat.get("is_anonymous"):
        return f"Аноним #{chat['id']}"
    return f"Раскрыт #{chat['id']}"


def get_psychologist_chats_keyboard(chats: List[dict], back_callback: str) -> InlineKeyboardMarkup:
    """Список чатов (активных или закрытых)."""
    builder = InlineKeyboardBuilder()
    for chat in chats:
        label = _chat_label(chat)
        msg_count = chat.get("msg_count", 0)
        builder.row(
            InlineKeyboardButton(
                text=f"{label}  [{msg_count} сообщ.]",
                callback_data=f"psych:chat:{chat['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data=back_callback))
    return builder.as_markup()


def get_psychologist_chat_reply_keyboard(chat_id: int, is_closed: bool) -> ReplyKeyboardMarkup:
    """ReplyKeyboard для режима чата — всегда видна у психолога."""
    buttons = []
    if not is_closed:
        buttons.append(KeyboardButton(text="🚪 Завершить чат"))
    buttons.append(KeyboardButton(text="◀️ К списку чатов"))
    return ReplyKeyboardMarkup(
        keyboard=[buttons],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Напишите ответ ученику...",
    )


def get_psychologist_in_chat_keyboard(chat_id: int, is_closed: bool) -> InlineKeyboardMarkup:
    """Клавиатура внутри чата для психолога."""
    builder = InlineKeyboardBuilder()
    if not is_closed:
        builder.row(
            InlineKeyboardButton(text="🚪 Завершить чат", callback_data=f"psych:close:{chat_id}"),
        )
    builder.row(
        InlineKeyboardButton(text="◀️ К списку чатов", callback_data="psych:exit_chat"),
    )
    return builder.as_markup()


def get_psychologist_notify_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Кнопка «Ответить» в уведомлении о новом сообщении."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💬 Ответить", callback_data=f"psych:chat:{chat_id}"),
    )
    return builder.as_markup()
