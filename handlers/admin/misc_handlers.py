"""
Хендлеры администратора: объявления, вопросы, статистика, ученики, рассылка.
"""
from aiogram import Router, F, Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from handlers.admin.common import is_admin, user_repo, grade_repo, announce_repo
from database.ticket_repository import TicketRepository
from handlers.states import AdminSendAnnouncement, AdminTicket
from keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_class_selection_keyboard,
    get_announcement_audience_keyboard,
    get_announcement_confirm_keyboard,
    get_tickets_list_keyboard,
    get_admin_ticket_closed_keyboard,
    get_stats_class_keyboard,
    get_cancel_keyboard,
)
from services.mailing_service import MailingService
from utils.config_loader import get_all_classes
from utils.pagination import paginate

router = Router()
ticket_repo = TicketRepository()


def _tickets_page_markup(tickets, page):
    page_items, has_prev, has_next = paginate(tickets, page)
    return get_tickets_list_keyboard(page_items, page=page, has_prev=has_prev, has_next=has_next)


def _format_ticket_history(messages: list) -> str:
    if not messages:
        return "Сообщений пока нет."
    lines = []
    for m in messages:
        time = m["created_at"][11:16]
        if m["sender_type"] == "student":
            name = m.get("sender_name") or "Ученик"
            lines.append(f"<b>{name}</b> [{time}]:\n{m['text']}")
        else:
            name = m.get("sender_name") or "Администратор"
            lines.append(f"<b>{name} (адм.)</b> [{time}]:\n{m['text']}")
    return "\n\n".join(lines)


async def _notify_student_ticket(bot: Bot, dp: Dispatcher, student_user_id: int,
                                  ticket_id: int, text: str) -> None:
    """Уведомить студента о новом сообщении в тикете. Если студент уже в чате — тихо."""
    key = StorageKey(bot_id=bot.id, chat_id=student_user_id, user_id=student_user_id)
    state_data = await dp.storage.get_data(key)
    student_in_thread = state_data.get("ticket_id") == ticket_id
    try:
        if student_in_thread:
            await bot.send_message(student_user_id, text, parse_mode="HTML")
        else:
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            kb = InlineKeyboardBuilder()
            kb.button(text="📋 Открыть обращение", callback_data=f"ticket_view:{ticket_id}")
            await bot.send_message(student_user_id, text, parse_mode="HTML", reply_markup=kb.as_markup())
    except Exception:
        pass


# ── Отмена ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text("Главное меню:", reply_markup=get_admin_main_menu())


# ── Ученики ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:students")
async def menu_students(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    students = user_repo.get_all_students()
    if not students:
        await callback.message.edit_text("Ни одного ученика не зарегистрировано.", reply_markup=get_admin_main_menu())
        return
    classes = {}
    for uid, name, cls in students:
        classes.setdefault(cls, []).append(name)
    text = f"Учеников в базе: <b>{len(students)}</b>\n\n"
    for cls, names in sorted(classes.items()):
        text += f"<b>{cls}</b> ({len(names)} чел.):\n"
        text += ", ".join(names) + "\n\n"
    await callback.message.edit_text(text.strip(), parse_mode="HTML", reply_markup=get_admin_main_menu())


# ── Объявления ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:announce")
async def menu_announce(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    classes = get_all_classes()
    await state.set_state(AdminSendAnnouncement.selecting_audience)
    await callback.message.edit_text(
        "Кому отправить объявление?",
        reply_markup=get_announcement_audience_keyboard(classes),
    )


@router.callback_query(AdminSendAnnouncement.selecting_audience, F.data.startswith("announce_target:"))
async def announce_select_target(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    target = callback.data.split(":", 1)[1]
    await state.update_data(announce_target=target)
    await state.set_state(AdminSendAnnouncement.entering_text)
    await callback.message.edit_text(
        "Отправь текст или фото с подписью:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AdminSendAnnouncement.entering_text, F.photo)
async def announce_receive_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    caption = message.caption or ""
    await state.update_data(announce_photo=file_id, announce_text=caption)
    data = await state.get_data()
    target = data["announce_target"]
    label = "всем ученикам" if target == "all" else f"классу {target}"
    await state.set_state(AdminSendAnnouncement.confirming)
    await message.answer_photo(
        file_id,
        caption=f"Отправить {label}?\n\n<b>Подпись:</b> {caption or '(нет)'}",
        parse_mode="HTML",
        reply_markup=get_announcement_confirm_keyboard(),
    )


@router.message(AdminSendAnnouncement.entering_text, F.text)
async def announce_enter_text(message: Message, state: FSMContext):
    await state.update_data(announce_text=message.text.strip(), announce_photo=None)
    data = await state.get_data()
    target = data["announce_target"]
    label = "всем ученикам" if target == "all" else f"классу {target}"
    await state.set_state(AdminSendAnnouncement.confirming)
    await message.answer(
        f"Отправить {label}?\n\n<b>Текст:</b>\n{message.text}",
        parse_mode="HTML",
        reply_markup=get_announcement_confirm_keyboard(),
    )


@router.callback_query(AdminSendAnnouncement.confirming, F.data == "announce_confirm")
async def confirm_announcement(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    text = data["announce_text"]
    target = data["announce_target"]
    photo_file_id = data.get("announce_photo")
    announce_repo.create(text, callback.from_user.id, target, photo_file_id=photo_file_id)
    if target == "all":
        students = user_repo.get_all_students()
        recipients = [(uid, name) for uid, name, _ in students]
    else:
        recipients = user_repo.get_students_by_class(target)
    mailing = MailingService(bot)
    send_text = f"📢 Объявление:\n\n{text}" if text else "📢 Объявление:"
    sent, failed = await mailing.send_text_to_users(recipients, send_text, photo_file_id=photo_file_id)
    await state.clear()
    result_text = f"✅ Объявление отправлено. Доставлено: {sent}. Ошибок: {failed}."
    if photo_file_id:
        await callback.message.edit_caption(caption=result_text, reply_markup=get_admin_main_menu())
    else:
        await callback.message.edit_text(result_text, reply_markup=get_admin_main_menu())


# ── Тикеты (обращения учеников) ───────────────────────────────────────────────

def _tickets_header() -> str:
    stats = ticket_repo.get_stats()
    return (
        f"📬 <b>Обращения учеников</b>\n"
        f"Всего: {stats['total']} | "
        f"Открытых: {stats['open']} | "
        f"Закрытых: {stats['closed']}"
    )


@router.callback_query(F.data == "menu:questions")
async def menu_tickets_admin(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    await state.clear()
    tickets = ticket_repo.get_all_open()
    header = _tickets_header()
    if not tickets:
        await callback.message.edit_text(
            header + "\n\nОткрытых обращений нет.",
            parse_mode="HTML",
            reply_markup=get_admin_main_menu(),
        )
        return
    await callback.message.edit_text(
        header, parse_mode="HTML",
        reply_markup=_tickets_page_markup(tickets, 0),
    )


@router.callback_query(F.data.startswith("tickets_page:"))
async def tickets_paginate(callback: CallbackQuery):
    await callback.answer()
    page = int(callback.data.split(":")[1])
    tickets = ticket_repo.get_all_open()
    header = _tickets_header()
    if not tickets:
        await callback.message.edit_text(
            header + "\n\nОткрытых обращений нет.",
            parse_mode="HTML",
            reply_markup=get_admin_main_menu(),
        )
        return
    await callback.message.edit_text(
        header, parse_mode="HTML",
        reply_markup=_tickets_page_markup(tickets, page),
    )


@router.callback_query(F.data.startswith("ticket_open:"))
async def admin_open_ticket(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    ticket_id = int(callback.data.split(":")[1])
    ticket = ticket_repo.get_ticket(ticket_id)
    if not ticket:
        await callback.message.edit_text("Обращение не найдено.", reply_markup=get_admin_main_menu())
        return
    messages = ticket_repo.get_messages(ticket_id)
    history = _format_ticket_history(messages)
    status = "🟢 Открыто" if ticket["status"] == "open" else "🔴 Закрыто"
    student_info = f"{ticket.get('student_name', '?')}, {ticket.get('student_class', '?')}"
    header = (
        f"📬 <b>Обращение #{ticket_id}</b> ({status})\n"
        f"<b>Ученик:</b> {student_info}\n\n"
    )
    text = header + history
    if ticket["status"] == "open":
        await state.set_state(AdminTicket.in_thread)
        await state.update_data(admin_ticket_id=ticket_id, ticket_student_id=ticket["student_user_id"])
        reply_kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🚪 Закрыть обращение"), KeyboardButton(text="◀️ К списку")]],
            resize_keyboard=True,
            one_time_keyboard=False,
            input_field_placeholder="Написать ответ...",
        )
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, parse_mode="HTML", reply_markup=reply_kb)
    else:
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=get_admin_ticket_closed_keyboard(),
        )


@router.message(AdminTicket.in_thread, F.text == "🚪 Закрыть обращение")
async def admin_close_ticket(message: Message, state: FSMContext, bot: Bot, dp: Dispatcher):
    data = await state.get_data()
    ticket_id = data.get("admin_ticket_id")
    student_id = data.get("ticket_student_id")
    ticket_repo.close(ticket_id)
    await state.clear()
    await message.answer(
        f"🔴 Обращение #{ticket_id} закрыто.",
        reply_markup=ReplyKeyboardRemove(),
    )
    if student_id:
        await _notify_student_ticket(
            bot, dp, student_id, ticket_id,
            f"🔴 Администратор закрыл обращение #{ticket_id}.",
        )


@router.message(AdminTicket.in_thread, F.text == "◀️ К списку")
async def admin_exit_ticket(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Выход из обращения.", reply_markup=ReplyKeyboardRemove())
    tickets = ticket_repo.get_all_open()
    header = _tickets_header()
    if not tickets:
        await message.answer(header + "\n\nОткрытых обращений нет.", parse_mode="HTML", reply_markup=get_admin_main_menu())
        return
    await message.answer(header, parse_mode="HTML", reply_markup=_tickets_page_markup(tickets, 0))


@router.message(AdminTicket.in_thread, F.text)
async def admin_ticket_reply(message: Message, state: FSMContext, bot: Bot, dp: Dispatcher):
    data = await state.get_data()
    ticket_id = data.get("admin_ticket_id")
    student_id = data.get("ticket_student_id")
    ticket = ticket_repo.get_ticket(ticket_id)
    if not ticket or ticket["status"] == "closed":
        await state.clear()
        await message.answer("Обращение уже закрыто.", reply_markup=ReplyKeyboardRemove())
        return
    admin = user_repo.get_user(message.from_user.id)
    admin_name = admin["ФИ"] if admin else "Администратор"
    ticket_repo.add_message(ticket_id, "admin", admin_name, message.text.strip())
    if student_id:
        notify_text = (
            f"💬 <b>Ответ по обращению #{ticket_id}</b>\n\n"
            f"<b>{admin_name}:</b> {message.text.strip()}"
        )
        await _notify_student_ticket(bot, dp, student_id, ticket_id, notify_text)


# ── Статистика по классу ───────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:stats")
async def menu_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    classes = get_all_classes()
    await callback.message.edit_text(
        "Выбери класс для просмотра статистики:",
        reply_markup=get_stats_class_keyboard(classes),
    )


@router.callback_query(F.data.startswith("stats_class:"))
async def stats_show_class(callback: CallbackQuery):
    await callback.answer()
    class_name = callback.data.split(":", 1)[1]
    stats = grade_repo.get_class_statistics(class_name)
    students = user_repo.get_students_by_class(class_name)

    avg = stats.get("average_grade")
    avg_text = f"{avg:.2f}" if avg else "нет данных"
    counts = stats.get("grade_counts", {})
    dist_lines = [
        f"  «{g}» — {counts.get(g, 0)} шт."
        for g in ("5", "4", "3", "2")
        if counts.get(g, 0)
    ]
    text = (
        f"<b>Статистика: {class_name}</b>\n"
        f"Учеников в системе: {len(students)}\n\n"
        f"Средний балл: <b>{avg_text}</b>\n"
    )
    if dist_lines:
        text += "Распределение оценок:\n" + "\n".join(dist_lines)
    else:
        text += "Оценок ещё не выставлено."
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_main_menu())
