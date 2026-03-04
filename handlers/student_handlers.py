"""
Handlers для функционала ученика.
"""
import logging
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.user_repository import UserRepository
from database.grade_repository import GradeRepository
from database.event_repository import EventRepository
from database.announcement_repository import AnnouncementRepository
from database.ticket_repository import TicketRepository
from handlers.states import StudentTicket
from keyboards.student_keyboards import (
    get_student_main_menu,
    get_events_keyboard,
    get_event_sections_keyboard,
    get_section_detail_keyboard,
    get_event_action_keyboard,
    get_cancel_registration_keyboard,
    get_my_events_keyboard,
    get_announcement_nav_keyboard,
    get_tickets_menu_keyboard,
    get_my_tickets_keyboard,
    get_student_ticket_reply_keyboard,
    get_student_ticket_closed_keyboard,
)
from keyboards.common_keyboards import get_cancel_keyboard
from services.grade_card_service import generate_grade_card

router = Router()
logger = logging.getLogger(__name__)

user_repo = UserRepository()
grade_repo = GradeRepository()
event_repo = EventRepository()
announce_repo = AnnouncementRepository()
ticket_repo = TicketRepository()


def _get_student(user_id: int):
    user = user_repo.get_user(user_id)
    if not user or user["isAdmin"]:
        return None
    return user


# ── Главное меню (инлайн) ─────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:card")
async def menu_card(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    name = user["ФИ"]
    class_name = user["class"]
    grades = grade_repo.get_student_grades(name)
    if not grades:
        await callback.message.edit_text(
            "📭 Оценки пока не выставлены. Обратись к администратору.",
            reply_markup=get_student_main_menu(),
        )
        return
    wait_msg = await callback.message.edit_text("⏳ Генерирую табель...")
    card_path = None
    try:
        card_path = await generate_grade_card(name, class_name)
        photo = FSInputFile(card_path)
        await callback.message.answer_photo(photo=photo, caption=f"📊 Табель успеваемости\n{name}, {class_name}")
        await wait_msg.edit_text("Что ещё хочешь сделать?", reply_markup=get_student_main_menu())
    except Exception as e:
        logger.exception("menu_card error for %s", name)
        await wait_msg.edit_text(
            f"❌ Ошибка при генерации табеля: {e}",
            reply_markup=get_student_main_menu(),
        )
    finally:
        if card_path and os.path.exists(card_path):
            try:
                os.remove(card_path)
            except OSError:
                pass


@router.message(Command("getcard"))
async def cmd_getcard(message: Message):
    user = _get_student(message.from_user.id)
    if not user:
        await message.answer("Вы не зарегистрированы. Используйте /start")
        return
    name = user["ФИ"]
    class_name = user["class"]
    grades = grade_repo.get_student_grades(name)
    if not grades:
        await message.answer("Оценки пока не выставлены.")
        return
    wait_msg = await message.answer("⏳ Генерирую табель...")
    try:
        card_path = await generate_grade_card(name, class_name)
        photo = FSInputFile(card_path)
        await message.answer_photo(photo=photo, caption=f"Табель: {name}")
    except Exception as e:
        await message.answer(f"Ошибка: {e}")
    finally:
        await wait_msg.delete()


@router.callback_query(F.data == "menu:events")
async def menu_events(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    events = event_repo.get_active_events()
    if not events:
        await callback.message.edit_text(
            "Сейчас нет активных мероприятий.",
            reply_markup=get_student_main_menu(),
        )
        return
    await callback.message.edit_text("📅 Выбери мероприятие:", reply_markup=get_events_keyboard(events))


async def _send_announcement(callback: CallbackQuery, items: list, page: int):
    """Отправляет одно объявление с навигацией. Всегда пересоздаёт сообщение."""
    from datetime import datetime
    item = items[page]
    dt = datetime.fromisoformat(item["created_at"]).strftime("%d.%m.%Y %H:%M")
    author = item.get("author_name") or "Администрация"
    target_label = "всем" if item["target"] == "all" else f"классу {item['target']}"
    text = (
        f"📢 <b>Объявление</b> — {dt}\n"
        f"👤 От: <b>{author}</b> | Кому: {target_label}\n\n"
        f"{item['text']}"
    )
    markup = get_announcement_nav_keyboard(page, len(items))
    photo = item.get("photo_file_id")

    try:
        await callback.message.delete()
    except Exception:
        pass

    if photo:
        await callback.message.answer_photo(photo, caption=text, parse_mode="HTML", reply_markup=markup)
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "menu:announcements")
async def menu_announcements(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    items = announce_repo.get_recent(limit=20, target=user["class"])
    if not items:
        await callback.message.edit_text(
            "Объявлений пока нет.",
            reply_markup=get_student_main_menu(),
        )
        return
    await _send_announcement(callback, items, 0)


@router.callback_query(F.data.startswith("ann_page:"))
async def ann_page(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    page = int(callback.data.split(":")[1])
    items = announce_repo.get_recent(limit=20, target=user["class"])
    if not items or page >= len(items):
        return
    await _send_announcement(callback, items, page)


@router.callback_query(F.data == "ann_noop")
async def ann_noop(callback: CallbackQuery):
    await callback.answer()


# ── Мероприятия ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("event_view:"))
async def view_event(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    if not event:
        await callback.message.edit_text("Мероприятие не найдено.")
        return
    class_name = user["class"]
    sections = event_repo.get_sections(event_id)
    desc = event.get("description") or ""
    total = event_repo.get_total_registrations(event_id)
    limit_text = f"\nЛимит от класса: {event['class_limit']} чел." if event.get("class_limit") else ""
    text = (
        f"<b>{event['title']}</b>\n"
        f"Дата: {event['date']}{limit_text}"
        + (f"\nЗаписалось: {total} чел." if total else "")
        + (f"\n\n{desc}" if desc else "")
    )

    if sections:
        user_section_ids = event_repo.get_user_sections(event_id, callback.from_user.id)
        section_counts = {s["id"]: event_repo.get_section_count(s["id"]) for s in sections}
        text += "\n\n<b>Выбери секцию:</b>"
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=get_event_sections_keyboard(
                event_id, sections,
                user_section_ids=user_section_ids,
                section_counts=section_counts,
            ),
        )
    else:
        is_registered = event_repo.is_registered(event_id, callback.from_user.id)
        is_full = not is_registered and not event_repo.is_event_available(
            event_id, class_name, event.get("class_limit")
        )
        status_text = "✅ Ты записан!" if is_registered else ("🔒 Мест от вашего класса нет." if is_full else "")
        if status_text:
            text += f"\n\n{status_text}"
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=get_event_action_keyboard(event_id, is_registered, is_full),
        )


@router.callback_query(F.data.startswith("section_view:"))
async def view_section(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    _, event_id_str, section_id_str = callback.data.split(":")
    event_id = int(event_id_str)
    section_id = int(section_id_str)
    section = event_repo.get_section(section_id)
    if not section:
        await callback.message.edit_text("Секция не найдена.")
        return
    count = event_repo.get_section_count(section_id)
    cap = section.get("capacity")
    user_sections = event_repo.get_user_sections(event_id, callback.from_user.id)
    is_registered = section_id in user_sections
    is_full = bool(cap and count >= cap) and not is_registered

    time_str = f"\n🕐 <b>Время:</b> {section['time']}" if section.get("time") else ""
    host_str = f"\n👤 <b>Ведущий:</b> {section['host']}" if section.get("host") else ""
    if cap:
        spots_left = cap - count
        spots_str = f"\n👥 <b>Мест:</b> {spots_left} из {cap}"
    else:
        spots_str = f"\n👥 <b>Записалось:</b> {count} чел."
    desc_str = f"\n\n{section['description']}" if section.get("description") else ""
    status_str = ""
    if is_registered:
        status_str = "\n\n✅ <b>Ты записан на эту секцию</b>"
    elif is_full:
        status_str = "\n\n🔒 <b>Мест нет</b>"

    text = f"<b>{section['title']}</b>{time_str}{host_str}{spots_str}{desc_str}{status_str}"
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=get_section_detail_keyboard(event_id, section_id, is_registered, is_full),
    )


@router.callback_query(F.data.startswith("event_reg_section:"))
async def register_for_section(callback: CallbackQuery):
    user = _get_student(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    _, event_id_str, section_id_str = callback.data.split(":")
    event_id = int(event_id_str)
    section_id = int(section_id_str)
    section = event_repo.get_section(section_id)
    if not section:
        await callback.answer("Секция не найдена.", show_alert=True)
        return
    if section.get("capacity"):
        count = event_repo.get_section_count(section_id)
        if count >= section["capacity"]:
            await callback.answer("Мест в этой секции нет.", show_alert=True)
            return
    success = event_repo.register_to_section(
        event_id, section_id, callback.from_user.id, user["ФИ"], user["class"]
    )
    if not success:
        await callback.answer("Ты уже записан на эту секцию.", show_alert=True)
        return
    time_str = f" в {section['time']}" if section.get("time") else ""
    await callback.answer(f"✅ Ты записан на «{section['title']}»{time_str}!", show_alert=True)
    await _refresh_section_message(callback.message, event_id, section_id, callback.from_user.id)


@router.callback_query(F.data.startswith("event_cancel_section:"))
async def cancel_section_registration(callback: CallbackQuery):
    await callback.answer()
    _, event_id_str, section_id_str = callback.data.split(":")
    event_id = int(event_id_str)
    section_id = int(section_id_str)
    section = event_repo.get_section(section_id)
    title = section["title"] if section else "секцию"
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да, отменить", callback_data=f"event_cancel_sec_confirm:{event_id}:{section_id}"),
        InlineKeyboardButton(text="❌ Нет", callback_data=f"section_view:{event_id}:{section_id}"),
    )
    await callback.message.edit_text(
        f"Отменить запись на секцию <b>{title}</b>?",
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("event_cancel_sec_confirm:"))
async def confirm_cancel_section(callback: CallbackQuery):
    _, event_id_str, section_id_str = callback.data.split(":")
    event_id = int(event_id_str)
    section_id = int(section_id_str)
    event_repo.unregister_from_section(event_id, section_id, callback.from_user.id)
    await callback.answer("Запись отменена.", show_alert=True)
    await _refresh_section_message(callback.message, event_id, section_id, callback.from_user.id)


async def _refresh_section_message(message, event_id: int, section_id: int, user_id: int):
    """Обновить экран детальной секции без вызова callback.answer()."""
    section = event_repo.get_section(section_id)
    if not section:
        return
    count = event_repo.get_section_count(section_id)
    cap = section.get("capacity")
    user_sections = event_repo.get_user_sections(event_id, user_id)
    is_registered = section_id in user_sections
    is_full = bool(cap and count >= cap) and not is_registered

    time_str = f"\n🕐 <b>Время:</b> {section['time']}" if section.get("time") else ""
    host_str = f"\n👤 <b>Ведущий:</b> {section['host']}" if section.get("host") else ""
    if cap:
        spots_left = cap - count
        spots_str = f"\n👥 <b>Мест:</b> {spots_left} из {cap}"
    else:
        spots_str = f"\n👥 <b>Записалось:</b> {count} чел."
    desc_str = f"\n\n{section['description']}" if section.get("description") else ""
    status_str = ""
    if is_registered:
        status_str = "\n\n✅ <b>Ты записан на эту секцию</b>"
    elif is_full:
        status_str = "\n\n🔒 <b>Мест нет</b>"

    text = f"<b>{section['title']}</b>{time_str}{host_str}{spots_str}{desc_str}{status_str}"
    await message.edit_text(
        text, parse_mode="HTML",
        reply_markup=get_section_detail_keyboard(event_id, section_id, is_registered, is_full),
    )


@router.callback_query(F.data.startswith("event_register:"))
async def register_for_event(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    if not event:
        return
    class_name = user["class"]
    if not event_repo.is_event_available(event_id, class_name, event.get("class_limit")):
        await callback.answer("Мест нет — лимит от вашего класса исчерпан.", show_alert=True)
        return
    success = event_repo.register(event_id, callback.from_user.id, user["ФИ"], class_name)
    if success:
        await callback.answer("Ты записан! ✅", show_alert=True)
    else:
        await callback.answer("Ты уже записан на это мероприятие.", show_alert=True)
    await view_event(callback)


@router.callback_query(F.data.startswith("event_cancel:"))
async def ask_cancel_registration(callback: CallbackQuery):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    title = event["title"] if event else "мероприятие"
    await callback.message.edit_text(
        f"Отменить запись на <b>{title}</b>?",
        parse_mode="HTML",
        reply_markup=get_cancel_registration_keyboard(event_id),
    )


@router.callback_query(F.data.startswith("event_cancel_confirm:"))
async def confirm_cancel_registration(callback: CallbackQuery):
    user = _get_student(callback.from_user.id)
    event_id = int(callback.data.split(":")[1])
    event_repo.unregister_from_event(event_id, callback.from_user.id)
    await callback.answer("Запись отменена.", show_alert=True)
    # Возвращаемся к экрану мероприятия
    event = event_repo.get_event(event_id)
    if not event:
        return
    is_registered = event_repo.is_registered(event_id, callback.from_user.id)
    is_full = not is_registered and not event_repo.is_event_available(
        event_id, user["class"] if user else "", event.get("class_limit")
    )
    desc = event.get("description") or ""
    text = f"<b>{event['title']}</b>\nДата: {event['date']}" + (f"\n\n{desc}" if desc else "")
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=get_event_action_keyboard(event_id, is_registered, is_full),
    )


@router.callback_query(F.data.startswith("event_section_full:"))
async def section_full(callback: CallbackQuery):
    await callback.answer("Мест в этой секции нет.", show_alert=True)


@router.callback_query(F.data.startswith("event_full:"))
async def event_full(callback: CallbackQuery):
    await callback.answer("Мест нет — лимит от вашего класса исчерпан.", show_alert=True)


@router.callback_query(F.data == "back_to_events")
async def back_to_events(callback: CallbackQuery):
    await callback.answer()
    events = event_repo.get_active_events()
    if not events:
        await callback.message.edit_text("Сейчас нет активных мероприятий.", reply_markup=get_student_main_menu())
        return
    await callback.message.edit_text("📅 Выбери мероприятие:", reply_markup=get_events_keyboard(events))


# ── Мои записи ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:my_events")
async def menu_my_events(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    events = event_repo.get_user_events(callback.from_user.id)
    if not events:
        await callback.message.edit_text(
            "📌 Ты пока не записан ни на одно мероприятие.",
            reply_markup=get_student_main_menu(),
        )
        return
    await callback.message.edit_text(
        "📌 <b>Твои записи на мероприятия:</b>",
        parse_mode="HTML",
        reply_markup=get_my_events_keyboard(events),
    )


# ── Обращения (тикеты) ────────────────────────────────────────────────────────

from aiogram import Dispatcher
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import ReplyKeyboardRemove


def _format_ticket_history(messages: list, student_name: str) -> str:
    if not messages:
        return "Сообщений пока нет. Напиши своё обращение!"
    lines = []
    for m in messages:
        time = m["created_at"][11:16]
        if m["sender_type"] == "student":
            lines.append(f"<b>Ты</b> [{time}]:\n{m['text']}")
        else:
            name = m.get("sender_name") or "Администратор"
            lines.append(f"<b>{name}</b> [{time}]:\n{m['text']}")
    return "\n\n".join(lines)


async def _notify_admins_ticket(bot: Bot, dp: Dispatcher, ticket_id: int,
                                 student_name: str, title: str, text: str) -> None:
    """Отправить уведомление всем незанятым этим тикетом админам."""
    from keyboards.admin_keyboards import get_tickets_list_keyboard
    admins = user_repo.get_all_admins()
    notify_text = (
        f"📬 <b>Новое сообщение в обращении #{ticket_id}</b>\n"
        f"<b>От:</b> {student_name}\n\n"
        f"<i>{text[:200]}</i>"
    )
    for admin_id, _ in admins:
        # Если этот админ уже смотрит тот же тикет — тихо (он увидит)
        key = StorageKey(bot_id=bot.id, chat_id=admin_id, user_id=admin_id)
        state_data = await dp.storage.get_data(key)
        if state_data.get("admin_ticket_id") == ticket_id:
            continue
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            from aiogram.utils.keyboard import InlineKeyboardBuilder
            kb = InlineKeyboardBuilder()
            kb.button(text="📋 Открыть обращение", callback_data=f"ticket_open:{ticket_id}")
            await bot.send_message(admin_id, notify_text, parse_mode="HTML", reply_markup=kb.as_markup())
        except Exception:
            pass


@router.callback_query(F.data == "menu:question")
async def menu_tickets(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    await state.clear()
    await callback.message.edit_text(
        "📬 <b>Обращения к администрации</b>\n\nЗдесь ты можешь написать вопрос или обращение и получить ответ от администратора.",
        parse_mode="HTML",
        reply_markup=get_tickets_menu_keyboard(),
    )


@router.callback_query(F.data == "ticket:new")
async def ticket_new(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    await state.set_state(StudentTicket.creating)
    await callback.message.edit_text(
        "✏️ Напиши своё обращение — его увидит администратор и ответит тебе здесь:",
        reply_markup=get_cancel_keyboard("ticket:cancel"),
    )


@router.message(StudentTicket.creating, F.text)
async def ticket_create_text(message: Message, state: FSMContext, bot: Bot, dp: Dispatcher):
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Пожалуйста, напиши более развернутое обращение.")
        return
    user = user_repo.get_user(message.from_user.id)
    if not user:
        await state.clear()
        return
    student_name = user["ФИ"]
    student_class = user.get("class", "")
    title = text[:80]
    ticket_id = ticket_repo.create(message.from_user.id, student_name, student_class, title)
    ticket_repo.add_message(ticket_id, "student", student_name, text)
    await state.set_state(StudentTicket.in_thread)
    await state.update_data(ticket_id=ticket_id)
    await message.answer(
        f"✅ <b>Обращение #{ticket_id} открыто</b>\n\nАдминистратор скоро ответит. "
        "Ты можешь продолжать писать сообщения — они добавятся в это обращение.",
        parse_mode="HTML",
        reply_markup=get_student_ticket_reply_keyboard(),
    )
    await _notify_admins_ticket(bot, dp, ticket_id, student_name, title, text)


@router.message(StudentTicket.in_thread, F.text == "🚪 Закрыть обращение")
async def ticket_student_close(message: Message, state: FSMContext, bot: Bot, dp: Dispatcher):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    ticket_repo.close(ticket_id)
    await state.clear()
    await message.answer(
        f"🔴 Обращение #{ticket_id} закрыто.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("🏠 Главное меню:", reply_markup=get_student_main_menu())
    # Уведомить админов что тикет закрыт
    admins = user_repo.get_all_admins()
    for admin_id, _ in admins:
        key = StorageKey(bot_id=bot.id, chat_id=admin_id, user_id=admin_id)
        state_data = await dp.storage.get_data(key)
        if state_data.get("admin_ticket_id") == ticket_id:
            try:
                await bot.send_message(
                    admin_id,
                    f"🔴 Ученик закрыл обращение #{ticket_id}.",
                )
            except Exception:
                pass


@router.message(StudentTicket.in_thread, F.text == "◀️ В главное меню")
async def ticket_student_to_menu(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("🏠 Главное меню:", reply_markup=ReplyKeyboardRemove())
    await message.answer("Выбери раздел:", reply_markup=get_student_main_menu())


@router.message(StudentTicket.in_thread, F.text)
async def ticket_student_message(message: Message, state: FSMContext, bot: Bot, dp: Dispatcher):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    ticket = ticket_repo.get_ticket(ticket_id)
    if not ticket or ticket["status"] == "closed":
        await state.clear()
        await message.answer(
            "Это обращение уже закрыто.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    user = user_repo.get_user(message.from_user.id)
    student_name = user["ФИ"] if user else "Ученик"
    ticket_repo.add_message(ticket_id, "student", student_name, message.text.strip())
    await _notify_admins_ticket(bot, dp, ticket_id, student_name, ticket["title"], message.text.strip())


@router.callback_query(F.data == "ticket:my")
async def my_tickets(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    await state.clear()
    tickets = ticket_repo.get_by_student(callback.from_user.id)
    if not tickets:
        await callback.message.edit_text(
            "У тебя пока нет обращений.",
            reply_markup=get_tickets_menu_keyboard(),
        )
        return
    await callback.message.edit_text(
        "📋 <b>Мои обращения:</b>",
        parse_mode="HTML",
        reply_markup=get_my_tickets_keyboard(tickets),
    )


@router.callback_query(F.data.startswith("ticket_view:"))
async def view_ticket(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    ticket_id = int(callback.data.split(":")[1])
    ticket = ticket_repo.get_ticket(ticket_id)
    if not ticket:
        await callback.message.edit_text("Обращение не найдено.", reply_markup=get_tickets_menu_keyboard())
        return
    messages = ticket_repo.get_messages(ticket_id)
    student_name = ticket.get("student_name", "")
    history = _format_ticket_history(messages, student_name)
    status = "🟢 Открыто" if ticket["status"] == "open" else "🔴 Закрыто"
    header = f"📬 <b>Обращение #{ticket_id}</b> ({status})\n\n"
    text = header + history
    if ticket["status"] == "open":
        await state.set_state(StudentTicket.in_thread)
        await state.update_data(ticket_id=ticket_id)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=get_student_ticket_reply_keyboard(),
        )
    else:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_student_ticket_closed_keyboard(),
        )


@router.callback_query(F.data == "ticket:cancel")
async def ticket_cancel(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "📬 <b>Обращения к администрации</b>",
        parse_mode="HTML",
        reply_markup=get_tickets_menu_keyboard(),
    )
