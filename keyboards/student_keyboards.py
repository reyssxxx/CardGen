"""
Клавиатуры для ученика.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Optional


HANDBOOK_URL = "https://lyceumsfedu.yonote.ru/share/98ef3601-f8d5-4ead-a4c1-5c505c5b683c"


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
    builder.row(
        InlineKeyboardButton(text="📌 Мои записи", callback_data="menu:my_events"),
        InlineKeyboardButton(text="💬 Психолог", callback_data="menu:support"),
    )
    builder.row(
        InlineKeyboardButton(text="📖 Хендбук лицеиста", url=HANDBOOK_URL),
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


def get_event_sections_keyboard(event_id: int, sections: List[dict],
                                 user_section_ids: Optional[List[int]] = None,
                                 section_counts: dict = None) -> InlineKeyboardMarkup:
    """
    Список секций мероприятия.
    Все секции ведут на экран детали (section_view:).
    user_section_ids — список секций, на которые уже записан ученик.
    """
    builder = InlineKeyboardBuilder()
    user_section_ids = user_section_ids or []
    section_counts = section_counts or {}
    for s in sections:
        count = section_counts.get(s["id"], 0)
        is_mine = s["id"] in user_section_ids
        cap = s.get("capacity")
        full = bool(cap and count >= cap) and not is_mine
        time_str = f"{s['time']} " if s.get("time") else ""
        if is_mine:
            label = f"✅ {time_str}{s['title']}"
        elif full:
            label = f"🔒 {time_str}{s['title']}"
        else:
            label = f"📌 {time_str}{s['title']}"
        builder.row(InlineKeyboardButton(text=label, callback_data=f"section_view:{event_id}:{s['id']}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_events"))
    return builder.as_markup()


def get_section_detail_keyboard(event_id: int, section_id: int,
                                 is_registered: bool, is_full: bool) -> InlineKeyboardMarkup:
    """Кнопки на экране детали секции."""
    builder = InlineKeyboardBuilder()
    if is_registered:
        builder.row(InlineKeyboardButton(
            text="❌ Отменить запись",
            callback_data=f"event_cancel_section:{event_id}:{section_id}",
        ))
    elif is_full:
        builder.row(InlineKeyboardButton(
            text="🔒 Мест нет",
            callback_data=f"event_section_full:{section_id}",
        ))
    else:
        builder.row(InlineKeyboardButton(
            text="✅ Записаться",
            callback_data=f"event_reg_section:{event_id}:{section_id}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад к секциям", callback_data=f"event_view:{event_id}"))
    return builder.as_markup()


def get_event_action_keyboard(event_id: int, is_registered: bool, is_full: bool) -> InlineKeyboardMarkup:
    """Кнопки записи/отмены записи на мероприятие (когда секций нет)."""
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


def get_announcement_nav_keyboard(page: int, total: int) -> InlineKeyboardMarkup:
    """Навигация по объявлениям: ← страница → + Назад."""
    builder = InlineKeyboardBuilder()
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️", callback_data=f"ann_page:{page - 1}"))
    nav.append(InlineKeyboardButton(text=f"{page + 1}/{total}", callback_data="ann_noop"))
    if page < total - 1:
        nav.append(InlineKeyboardButton(text="▶️", callback_data=f"ann_page:{page + 1}"))
    builder.row(*nav)
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:back_student"))
    return builder.as_markup()


def get_tickets_menu_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела обращений."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✏️ Новое обращение", callback_data="ticket:new"))
    builder.row(InlineKeyboardButton(text="📋 Мои обращения", callback_data="ticket:my"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:back_student"))
    return builder.as_markup()


def get_my_tickets_keyboard(tickets: List[dict]) -> InlineKeyboardMarkup:
    """Список обращений ученика."""
    builder = InlineKeyboardBuilder()
    for t in tickets:
        date_str = t["created_at"][:10] if t.get("created_at") else ""
        status = "🟢" if t.get("status") == "open" else "🔴"
        short = t["title"][:35] + "…" if len(t["title"]) > 35 else t["title"]
        label = f"{status} {short} — {date_str}"
        builder.row(InlineKeyboardButton(text=label, callback_data=f"ticket_view:{t['id']}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:question"))
    return builder.as_markup()


def get_student_ticket_reply_keyboard() -> ReplyKeyboardMarkup:
    """ReplyKeyboard во время активного чата по тикету."""
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="🚪 Закрыть обращение"),
            KeyboardButton(text="◀️ В главное меню"),
        ]],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Написать сообщение...",
    )


def get_student_ticket_closed_keyboard() -> InlineKeyboardMarkup:
    """Кнопка для просмотра закрытого тикета."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Мои обращения", callback_data="ticket:my"))
    return builder.as_markup()


def get_support_open_keyboard(has_active_chat: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if has_active_chat:
        builder.row(InlineKeyboardButton(text="💬 Продолжить чат", callback_data="support:open"))
    else:
        builder.row(InlineKeyboardButton(text="💬 Открыть анонимный чат", callback_data="support:create"))
    builder.row(
        InlineKeyboardButton(text="📋 История чатов", callback_data="support:history"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="menu:back_student"),
    )
    return builder.as_markup()


def get_student_chat_reply_keyboard(is_anonymous: bool) -> ReplyKeyboardMarkup:
    """ReplyKeyboard для режима чата с психологом — всегда видна у студента."""
    buttons = []
    if is_anonymous:
        buttons.append(KeyboardButton(text="👤 Открыть личность"))
    buttons.append(KeyboardButton(text="🚪 Завершить чат"))
    buttons.append(KeyboardButton(text="◀️ В главное меню"))
    return ReplyKeyboardMarkup(
        keyboard=[buttons],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder="Напишите сообщение психологу...",
    )


def get_support_chat_keyboard(is_anonymous: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_anonymous:
        builder.row(InlineKeyboardButton(text="👤 Открыть личность", callback_data="support:reveal"))
    builder.row(
        InlineKeyboardButton(text="🚪 Завершить чат", callback_data="support:close"),
        InlineKeyboardButton(text="◀️ В главное меню", callback_data="support:menu"),
    )
    return builder.as_markup()


def get_support_confirm_keyboard(action: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"support:confirm_{action}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="support:cancel_action"),
    )
    return builder.as_markup()


def get_support_history_keyboard(chats: List[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for chat in chats:
        label = f"Чат #{chat['id']} — {chat['created_at'][:10]}"
        builder.row(InlineKeyboardButton(text=label, callback_data=f"support:view_history:{chat['id']}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu:support"))
    return builder.as_markup()


def get_support_back_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💬 Открыть чат", callback_data="menu:support"))
    return builder.as_markup()
