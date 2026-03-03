"""
Handlers для функционала ученика.
"""
import logging
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from database.user_repository import UserRepository
from database.grade_repository import GradeRepository
from database.event_repository import EventRepository
from database.announcement_repository import AnnouncementRepository
from database.anon_question_repository import AnonQuestionRepository
from handlers.states import StudentQuestion
from keyboards.student_keyboards import (
    get_student_main_menu,
    get_events_keyboard,
    get_event_sections_keyboard,
    get_section_action_keyboard,
    get_cancel_section_keyboard,
    get_event_action_keyboard,
    get_cancel_registration_keyboard,
    get_questions_menu_keyboard,
    get_question_confirm_keyboard,
    get_my_questions_keyboard,
    get_question_detail_keyboard,
    get_announcement_nav_keyboard,
)
from keyboards.common_keyboards import get_cancel_keyboard
from services.grade_card_service import generate_grade_card
from utils.config_loader import get_all_classes

router = Router()
logger = logging.getLogger(__name__)

user_repo = UserRepository()
grade_repo = GradeRepository()
event_repo = EventRepository()
announce_repo = AnnouncementRepository()
anon_repo = AnonQuestionRepository()


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
        await callback.message.answer_photo(
            photo=photo,
            caption=f"📊 Табель успеваемости\n{name}, {class_name}",
        )
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
            "Нет актуальных мероприятий.",
            reply_markup=get_student_main_menu(),
        )
        return
    await callback.message.edit_text("📅 Актуальные мероприятия:", reply_markup=get_events_keyboard(events))


async def _show_announcement(callback: CallbackQuery, items: list, index: int):
    """Показать одно объявление с навигацией. Обрабатывает фото."""
    from datetime import datetime
    item = items[index]
    dt = datetime.fromisoformat(item["created_at"]).strftime("%d.%m.%Y %H:%M")
    author = item.get("author_name") or "Администрация"
    target = item.get("target", "all")
    target_text = "всем" if target == "all" else f"классу {target}"
    header = f"<b>📢 Объявление</b>\n<b>От:</b> {author} · {target_text}\n<b>Дата:</b> {dt}\n\n"
    body = item.get("text") or ""
    full_text = header + body
    photo = item.get("photo_file_id")
    markup = get_announcement_nav_keyboard(index, len(items))
    if photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(photo=photo, caption=full_text, parse_mode="HTML", reply_markup=markup)
    else:
        try:
            await callback.message.edit_text(full_text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await callback.message.answer(full_text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data == "menu:announcements")
async def menu_announcements(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    items = announce_repo.get_recent(limit=10, target=user["class"])
    if not items:
        await callback.message.edit_text(
            "Объявлений пока нет.",
            reply_markup=get_student_main_menu(),
        )
        return
    await _show_announcement(callback, items, 0)


@router.callback_query(F.data.startswith("ann:"))
async def navigate_announcement(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    index = int(callback.data.split(":")[1])
    items = announce_repo.get_recent(limit=10, target=user["class"])
    if not items or index >= len(items):
        await callback.message.edit_text("Объявлений пока нет.", reply_markup=get_student_main_menu())
        return
    await _show_announcement(callback, items, index)


@router.callback_query(F.data == "ann_noop")
async def ann_noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data == "menu:question")
async def menu_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    await callback.message.edit_text(
        "Здесь ты можешь задать вопрос администрации или посмотреть ответы на свои вопросы.\n\n"
        "ℹ️ Администратор увидит твоё имя и класс.",
        reply_markup=get_questions_menu_keyboard(),
    )


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

    sections = event_repo.get_sections(event_id)

    if sections:
        # Новый формат: день с секциями
        user_sections = event_repo.get_user_sections(event_id, callback.from_user.id)
        desc = event.get("description") or ""
        registered_count = len(user_sections)
        status = f"\n\n✅ Ты записан на {registered_count} секций" if registered_count else ""
        text = (
            f"<b>📅 {event['title']}</b>\nДата: {event['date']}"
            + (f"\n\n{desc}" if desc else "")
            + status
            + "\n\nВыбери секцию:"
        )
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=get_event_sections_keyboard(event_id, sections, user_sections),
        )
    else:
        # Старый формат: без секций
        class_name = user["class"]
        is_registered = event_repo.is_registered(event_id, callback.from_user.id)
        is_full = not is_registered and not event_repo.is_event_available(
            event_id, class_name, event.get("class_limit")
        )
        total = event_repo.get_total_registrations(event_id)
        desc = event.get("description") or ""
        limit_text = f"\nЛимит от класса: {event['class_limit']} чел." if event.get("class_limit") else ""
        registered_text = f"\nЗаписалось: {total} чел." if total else ""
        status_text = "✅ Ты записан!" if is_registered else ("🔒 Мест от вашего класса нет." if is_full else "")
        text = (
            f"<b>{event['title']}</b>\n"
            f"Дата: {event['date']}{limit_text}{registered_text}"
            + (f"\n\n{desc}" if desc else "")
            + (f"\n\n{status_text}" if status_text else "")
        )
        await callback.message.edit_text(
            text, parse_mode="HTML",
            reply_markup=get_event_action_keyboard(event_id, is_registered, is_full),
        )


# ── Секции: просмотр и запись ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("sec_view:"))
async def view_section(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    section_id = int(callback.data.split(":")[1])
    section = event_repo.get_section(section_id)
    if not section:
        await callback.message.edit_text("Секция не найдена.", reply_markup=get_student_main_menu())
        return
    event_id = section["event_id"]
    is_registered = event_repo.is_registered_section(section_id, callback.from_user.id)
    is_full = not is_registered and not event_repo.is_section_available(section_id)
    count = event_repo.get_section_registration_count(section_id)

    time_str = f"\n🕐 Время: {section['time']}" if section.get('time') else ""
    host_str = f"\n👤 Ведущий: {section['host']}" if section.get('host') else ""
    desc_str = f"\n\n{section['description']}" if section.get('description') else ""
    if section.get('capacity'):
        free = section['capacity'] - count
        cap_str = f"\n👥 Свободных мест: {free} из {section['capacity']}"
    else:
        cap_str = f"\n👥 Записалось: {count}" if count else ""
    status_text = "\n\n✅ Ты записан!" if is_registered else ""

    text = f"<b>{section['title']}</b>{time_str}{host_str}{cap_str}{desc_str}{status_text}"
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=get_section_action_keyboard(section_id, event_id, is_registered, is_full),
    )


@router.callback_query(F.data.startswith("sec_register:"))
async def register_for_section(callback: CallbackQuery):
    user = _get_student(callback.from_user.id)
    if not user:
        await callback.answer()
        return
    section_id = int(callback.data.split(":")[1])
    section = event_repo.get_section(section_id)
    if not section:
        await callback.answer()
        return
    if not event_repo.is_section_available(section_id):
        await callback.answer("Мест нет!", show_alert=True)
        return
    success = event_repo.register_section(
        section["event_id"], section_id, callback.from_user.id, user["ФИ"], user["class"]
    )
    # Показываем алерт (он же подтверждает callback)
    if success:
        await callback.answer("Ты записан! ✅", show_alert=True)
    else:
        await callback.answer("Ты уже записан на эту секцию.", show_alert=True)
    # Обновляем сообщение напрямую, не через view_section (там снова вызывается callback.answer)
    await _refresh_section_message(callback.message, section_id, callback.from_user.id)


async def _refresh_section_message(message, section_id: int, user_id: int):
    """Обновляет сообщение с карточкой секции без повторного answer()."""
    section = event_repo.get_section(section_id)
    if not section:
        return
    event_id = section["event_id"]
    is_registered = event_repo.is_registered_section(section_id, user_id)
    is_full = not is_registered and not event_repo.is_section_available(section_id)
    count = event_repo.get_section_registration_count(section_id)

    time_str = f"\n🕐 Время: {section['time']}" if section.get('time') else ""
    host_str = f"\n👤 Ведущий: {section['host']}" if section.get('host') else ""
    desc_str = f"\n\n{section['description']}" if section.get('description') else ""
    if section.get('capacity'):
        free = section['capacity'] - count
        cap_str = f"\n👥 Свободных мест: {free} из {section['capacity']}"
    else:
        cap_str = f"\n👥 Записалось: {count}" if count else ""
    status_text = "\n\n✅ Ты записан!" if is_registered else ""

    text = f"<b>{section['title']}</b>{time_str}{host_str}{cap_str}{desc_str}{status_text}"
    await message.edit_text(
        text, parse_mode="HTML",
        reply_markup=get_section_action_keyboard(section_id, event_id, is_registered, is_full),
    )


@router.callback_query(F.data.startswith("sec_full:"))
async def section_full(callback: CallbackQuery):
    await callback.answer("Мест нет!", show_alert=True)


@router.callback_query(F.data.startswith("sec_cancel:"))
async def ask_cancel_section(callback: CallbackQuery):
    await callback.answer()
    section_id = int(callback.data.split(":")[1])
    section = event_repo.get_section(section_id)
    title = section["title"] if section else "секцию"
    event_id = section["event_id"] if section else 0
    await callback.message.edit_text(
        f"Отменить запись на <b>{title}</b>?",
        parse_mode="HTML",
        reply_markup=get_cancel_section_keyboard(section_id, event_id),
    )


@router.callback_query(F.data.startswith("sec_cancel_confirm:"))
async def confirm_cancel_section(callback: CallbackQuery):
    section_id = int(callback.data.split(":")[1])
    event_repo.unregister_section(section_id, callback.from_user.id)
    await callback.answer("Запись отменена.", show_alert=True)
    await _refresh_section_message(callback.message, section_id, callback.from_user.id)


# ── Старые мероприятия (обратная совместимость) ───────────────────────────────

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
    success = event_repo.register(event_id, callback.from_user.id, "", user["ФИ"], class_name)
    if success:
        await callback.answer("Ты записан! ✅", show_alert=True)
    else:
        await callback.answer("Ты уже записан на это мероприятие.", show_alert=True)
    await view_event(callback)


@router.callback_query(F.data.startswith("event_full:"))
async def event_full(callback: CallbackQuery):
    await callback.answer("Мест нет — лимит от вашего класса исчерпан.", show_alert=True)


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
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event_repo.unregister_from_event(event_id, callback.from_user.id)
    await callback.answer("Запись отменена.", show_alert=True)
    await view_event(callback)


@router.callback_query(F.data == "back_to_events")
async def back_to_events(callback: CallbackQuery):
    await callback.answer()
    events = event_repo.get_active_events()
    if not events:
        await callback.message.edit_text("Нет актуальных мероприятий.", reply_markup=get_student_main_menu())
        return
    await callback.message.edit_text("📅 Актуальные мероприятия:", reply_markup=get_events_keyboard(events))


# ── Вопросы ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "q:new")
async def start_new_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    await state.set_state(StudentQuestion.entering_question)
    await callback.message.edit_text(
        "Напиши свой вопрос администрации.\nℹ️ Администратор увидит твоё имя.",
        reply_markup=get_cancel_keyboard("question_cancel"),
    )


@router.callback_query(F.data == "q:my")
async def my_questions(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    questions = anon_repo.get_by_user(callback.from_user.id)
    if not questions:
        await callback.message.edit_text(
            "Ты ещё не задавал вопросов.",
            reply_markup=get_questions_menu_keyboard(),
        )
        return
    await callback.message.edit_text(
        "Твои вопросы:",
        reply_markup=get_my_questions_keyboard(questions),
    )


@router.callback_query(F.data.startswith("my_q_view:"))
async def view_my_question(callback: CallbackQuery):
    await callback.answer()
    q_id = int(callback.data.split(":")[1])
    q = anon_repo.get_by_id(q_id)
    if not q:
        await callback.message.edit_text("Вопрос не найден.", reply_markup=get_questions_menu_keyboard())
        return
    from datetime import datetime
    dt = datetime.fromisoformat(q["created_at"]).strftime("%d.%m.%Y %H:%M")
    status = "✅ Отвечен" if q["answered"] else "⏳ Ожидает ответа"
    q_text = q.get("text") or ""
    q_photo = q.get("photo_file_id")
    text = f"<b>Дата:</b> {dt}\n<b>Статус:</b> {status}\n\n<i>{q_text}</i>" if q_text else f"<b>Дата:</b> {dt}\n<b>Статус:</b> {status}"
    markup = get_question_detail_keyboard()

    # Показываем фото вопроса если есть
    try:
        await callback.message.delete()
    except Exception:
        pass
    if q_photo:
        await callback.message.answer_photo(q_photo, caption=text, parse_mode="HTML", reply_markup=markup)
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)

    # Если отвечен — дополнительно показываем ответ отдельным сообщением
    if q["answered"] and (q.get("answer") or q.get("answer_photo_file_id")):
        answer_text = f"<b>💬 Ответ администрации:</b>\n{q['answer']}" if q.get("answer") else "<b>💬 Ответ администрации:</b>"
        ans_photo = q.get("answer_photo_file_id")
        if ans_photo:
            await callback.message.answer_photo(ans_photo, caption=answer_text, parse_mode="HTML")
        else:
            await callback.message.answer(answer_text, parse_mode="HTML")


@router.message(StudentQuestion.entering_question, F.photo)
async def process_question_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    text = message.caption.strip() if message.caption else ""
    await state.update_data(question_text=text, question_photo=photo_id)
    await state.set_state(StudentQuestion.confirming)
    caption = f"Твой вопрос:\n\n<i>{text}</i>\n\nОтправить?" if text else "Твой вопрос (фото без текста)\n\nОтправить?"
    await message.answer_photo(
        photo_id,
        caption=caption,
        parse_mode="HTML",
        reply_markup=get_question_confirm_keyboard(),
    )


@router.message(StudentQuestion.entering_question, F.text)
async def process_question_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Пожалуйста, напиши более развернутый вопрос.")
        return
    await state.update_data(question_text=text, question_photo=None)
    await state.set_state(StudentQuestion.confirming)
    await message.answer(
        f"Твой вопрос:\n\n<i>{text}</i>\n\nОтправить?",
        parse_mode="HTML",
        reply_markup=get_question_confirm_keyboard(),
    )


@router.callback_query(StudentQuestion.confirming, F.data == "question_confirm")
async def confirm_question(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    text = data["question_text"]
    photo_id = data.get("question_photo")
    question_id = anon_repo.create(text, asker_user_id=callback.from_user.id, photo_file_id=photo_id)
    await state.clear()

    user = user_repo.get_user(callback.from_user.id)
    student_info = f"{user['ФИ']}, {user['class']}" if user else "Неизвестный"

    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Ответить", callback_data=f"question_answer:{question_id}")
    kb.button(text="🗑 Удалить", callback_data=f"question_delete_ask:{question_id}")
    kb.adjust(2)

    notify_text = (
        f"❓ Новый вопрос от ученика\n"
        f"<b>От:</b> {student_info}\n\n"
        f"<i>{text}</i>" if text else
        f"❓ Новый вопрос от ученика\n"
        f"<b>От:</b> {student_info}"
    )

    admins = user_repo.get_all_admins()
    for admin_id, _ in admins:
        try:
            if photo_id:
                await bot.send_photo(admin_id, photo_id, caption=notify_text,
                                     parse_mode="HTML", reply_markup=kb.as_markup())
            else:
                await bot.send_message(admin_id, notify_text, parse_mode="HTML", reply_markup=kb.as_markup())
        except Exception:
            pass

    await callback.message.edit_text(
        "✅ Вопрос отправлен!",
        reply_markup=get_questions_menu_keyboard(),
    )


@router.callback_query(F.data == "question_cancel")
async def cancel_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "Здесь ты можешь задать вопрос администрации или посмотреть ответы на свои вопросы.\n\n"
        "ℹ️ Администратор увидит твоё имя и класс.",
        reply_markup=get_questions_menu_keyboard(),
    )
