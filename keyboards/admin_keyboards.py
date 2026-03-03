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
        InlineKeyboardButton(text="📝 Оценки класса", callback_data="menu:view_grades"),
        InlineKeyboardButton(text="📈 Статистика", callback_data="menu:stats"),
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


def get_event_description_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="event_skip_desc"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"),
    )
    return builder.as_markup()


def get_event_manage_day_keyboard(event_id: int, sections: list, published: bool) -> InlineKeyboardMarkup:
    """Экран управления днём мероприятий: список секций + действия."""
    builder = InlineKeyboardBuilder()
    for s in sections:
        time_str = f"{s['time']} " if s.get('time') else ""
        cap = f" (лимит {s['capacity']})" if s.get('capacity') else ""
        label = f"📌 {time_str}{s['title']}{cap}"
        builder.row(InlineKeyboardButton(text=label[:64], callback_data=f"adm_section_view:{s['id']}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить секцию", callback_data=f"section_add:{event_id}"))
    if not published and sections:
        builder.row(InlineKeyboardButton(text="✅ Опубликовать и уведомить", callback_data=f"event_publish:{event_id}"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"))
    return builder.as_markup()


def get_section_skip_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    """Пропустить/Отмена для полей секции."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data=callback_data),
        InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"),
    )
    return builder.as_markup()


def get_section_capacity_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Без лимита", callback_data="sec_cap:0"),
        InlineKeyboardButton(text="10", callback_data="sec_cap:10"),
        InlineKeyboardButton(text="15", callback_data="sec_cap:15"),
    )
    builder.row(
        InlineKeyboardButton(text="20", callback_data="sec_cap:20"),
        InlineKeyboardButton(text="30", callback_data="sec_cap:30"),
        InlineKeyboardButton(text="✏️ Другое", callback_data="sec_cap:custom"),
    )
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"))
    return builder.as_markup()


def get_admin_section_detail_keyboard(section_id: int, event_id: int) -> InlineKeyboardMarkup:
    """Просмотр секции админом: удалить / назад."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить секцию", callback_data=f"section_delete:{section_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="◀️ Назад к мероприятию", callback_data=f"event_manage:{event_id}"),
    )
    return builder.as_markup()


def get_admin_events_keyboard(events: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for event in events:
        active = event.get("is_active")
        pub = event.get("published", 1)
        if not active:
            status = "🔴"
        elif not pub:
            status = "📝"  # черновик
        else:
            status = "🟢"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {event['title']} — {event['date']}",
                callback_data=f"admin_event_view:{event['id']}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_cancel"))
    return builder.as_markup()


def get_event_manage_keyboard(event_id: int, is_active: bool, has_sections: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_sections:
        builder.row(
            InlineKeyboardButton(text="📋 Управление секциями", callback_data=f"event_manage:{event_id}"),
        )
    builder.row(
        InlineKeyboardButton(text="📥 Скачать список", callback_data=f"event_export:{event_id}"),
    )
    if is_active:
        builder.row(
            InlineKeyboardButton(text="🗑 Архивировать", callback_data=f"event_archive:{event_id}"),
        )
    builder.row(
        InlineKeyboardButton(text="❌ Удалить навсегда", callback_data=f"event_delete_ask:{event_id}"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_events_back"))
    return builder.as_markup()


def get_event_delete_confirm_keyboard(event_id: int) -> InlineKeyboardMarkup:
    """Подтверждение полного удаления мероприятия."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить навсегда", callback_data=f"event_delete:{event_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"admin_event_view:{event_id}"),
    )
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
    from datetime import datetime
    builder = InlineKeyboardBuilder()
    for q in questions:
        prefix = "❓" if not q["answered"] else "✅"
        try:
            dt = datetime.fromisoformat(q["created_at"]).strftime("%d.%m")
        except (ValueError, TypeError):
            dt = ""
        author = q.get("author_name") or "?"
        short = q["text"][:30] + ("..." if len(q["text"]) > 30 else "")
        label = f"{prefix} {dt} {author}: {short}"
        builder.row(
            InlineKeyboardButton(
                text=label[:64],
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
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"question_delete_ask:{question_id}"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="questions_back"),
    )
    return builder.as_markup()


def get_question_delete_confirm_keyboard(question_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления вопроса."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"question_delete:{question_id}"),
        InlineKeyboardButton(text="◀️ Отмена", callback_data=f"question_view:{question_id}"),
    )
    return builder.as_markup()



def get_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel"))
    return builder.as_markup()


def get_stats_class_keyboard(classes: List[str]) -> InlineKeyboardMarkup:
    """Выбор класса для просмотра статистики."""
    builder = InlineKeyboardBuilder()
    for cls in classes:
        builder.button(text=cls, callback_data=f"stats_class:{cls}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_cancel"))
    return builder.as_markup()
