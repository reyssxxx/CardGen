"""
Клавиатуры для администратора.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List


def get_admin_main_menu() -> InlineKeyboardMarkup:
    """Главное меню администратора (инлайн)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Загрузить оценки", callback_data="menu:grades"),
        InlineKeyboardButton(text="📤 Разослать табели", callback_data="menu:send_cards"),
    )
    builder.row(
        InlineKeyboardButton(text="🎉 Создать мероприятие", callback_data="menu:create_event"),
        InlineKeyboardButton(text="📋 Мероприятия", callback_data="menu:events_admin"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Объявление", callback_data="menu:announce"),
        InlineKeyboardButton(text="❓ Вопросы", callback_data="menu:questions"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Ученики", callback_data="menu:students"),
    )
    return builder.as_markup()


def get_class_selection_keyboard(classes: List[str], callback_prefix: str = "admin_class") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cls in classes:
        builder.button(text=cls, callback_data=f"{callback_prefix}:{cls}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"))
    return builder.as_markup()


def get_grade_upload_action_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📥 Загрузить Excel", callback_data="grade_upload_file"),
        InlineKeyboardButton(text="📋 Скачать шаблон", callback_data="grade_download_template"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"))
    return builder.as_markup()


def get_grade_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Сохранить", callback_data="grade_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"),
    )
    return builder.as_markup()


def get_send_cards_keyboard(classes: List[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Всем ученикам", callback_data="cards_class:all"))
    for cls in classes:
        builder.button(text=cls, callback_data=f"cards_class:{cls}")
    builder.adjust(1, 3)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"))
    return builder.as_markup()


def get_send_cards_confirm_keyboard(target: str, count: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"✅ Разослать {count} ученикам",
            callback_data=f"cards_confirm:{target}",
        ),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"),
    )
    return builder.as_markup()


def get_event_limit_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Без лимита", callback_data="event_limit:0"),
        InlineKeyboardButton(text="5", callback_data="event_limit:5"),
        InlineKeyboardButton(text="10", callback_data="event_limit:10"),
    )
    builder.row(
        InlineKeyboardButton(text="15", callback_data="event_limit:15"),
        InlineKeyboardButton(text="20", callback_data="event_limit:20"),
        InlineKeyboardButton(text="✏️ Другое", callback_data="event_limit:custom"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"))
    return builder.as_markup()


def get_event_description_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="event_skip_desc"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"),
    )
    return builder.as_markup()


def get_event_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Создать", callback_data="event_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"),
    )
    return builder.as_markup()


def get_admin_events_keyboard(events: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for event in events:
        status = "🟢" if event.get("is_active") else "🔴"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {event['title']} — {event['date']}",
                callback_data=f"admin_event_view:{event['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_cancel"))
    return builder.as_markup()


def get_event_manage_keyboard(event_id: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📥 Скачать список", callback_data=f"event_export:{event_id}"),
    )
    if is_active:
        builder.row(
            InlineKeyboardButton(text="🗑 Архивировать", callback_data=f"event_archive:{event_id}"),
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_events_back"))
    return builder.as_markup()


def get_announcement_audience_keyboard(classes: List[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Всем ученикам", callback_data="announce_target:all"))
    for cls in classes:
        builder.button(text=cls, callback_data=f"announce_target:{cls}")
    builder.adjust(1, 3)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"))
    return builder.as_markup()


def get_announcement_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Отправить", callback_data="announce_confirm"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"),
    )
    return builder.as_markup()


def get_questions_keyboard(questions: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for q in questions:
        prefix = "❓" if not q["answered"] else "✅"
        short = q["text"][:40] + ("..." if len(q["text"]) > 40 else "")
        builder.row(
            InlineKeyboardButton(
                text=f"{prefix} {short}",
                callback_data=f"question_view:{q['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_cancel"))
    return builder.as_markup()


def get_question_actions_keyboard(question_id: int, answered: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not answered:
        builder.row(
            InlineKeyboardButton(text="✏️ Ответить", callback_data=f"question_answer:{question_id}"),
        )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"question_delete:{question_id}"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="questions_back"),
    )
    return builder.as_markup()


def get_answer_audience_keyboard(classes: List[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="👥 Всем ученикам", callback_data="answer_target:all"))
    for cls in classes:
        builder.button(text=cls, callback_data=f"answer_target:{cls}")
    builder.adjust(1, 3)
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"))
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"))
    return builder.as_markup()
