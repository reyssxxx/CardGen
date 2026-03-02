"""
Handlers для функционала ученика.
"""
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
from handlers.states import StudentAnonQuestion
from keyboards.student_keyboards import (
    get_student_main_menu,
    get_events_keyboard,
    get_event_action_keyboard,
    get_cancel_registration_keyboard,
    get_question_confirm_keyboard,
    get_my_events_keyboard,
)
from keyboards.common_keyboards import get_cancel_keyboard
from services.grade_card_service import generate_grade_card
from utils.config_loader import get_all_classes

router = Router()

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
    await callback.message.edit_text("⏳ Генерирую табель...")
    try:
        card_path = await generate_grade_card(name, class_name)
        photo = FSInputFile(card_path)
        await callback.message.answer_photo(photo=photo, caption=f"📊 Табель успеваемости\n{name}, {class_name}")
        await callback.message.edit_text("Что ещё хочешь сделать?", reply_markup=get_student_main_menu())
    except Exception as e:
        await callback.message.edit_text(
            f"Ошибка при генерации табеля: {e}",
            reply_markup=get_student_main_menu(),
        )


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


@router.callback_query(F.data == "menu:announcements")
async def menu_announcements(callback: CallbackQuery):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    items = announce_repo.get_recent(limit=5, target=user["class"])
    if not items:
        await callback.message.edit_text(
            "Объявлений пока нет.",
            reply_markup=get_student_main_menu(),
        )
        return
    from datetime import datetime
    text = "<b>Последние объявления:</b>\n\n"
    for item in items:
        dt = datetime.fromisoformat(item["created_at"]).strftime("%d.%m.%Y")
        text += f"<b>{dt}</b>\n{item['text']}\n\n"
    await callback.message.edit_text(text.strip(), parse_mode="HTML", reply_markup=get_student_main_menu())


@router.callback_query(F.data == "menu:question")
async def menu_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user = _get_student(callback.from_user.id)
    if not user:
        return
    await state.set_state(StudentAnonQuestion.entering_question)
    await callback.message.edit_text(
        "Твой вопрос будет отправлен администратору анонимно.\n\nНапиши свой вопрос:",
        reply_markup=get_cancel_keyboard("question_cancel"),
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


# ── Анонимные вопросы ─────────────────────────────────────────────────────────

@router.message(StudentAnonQuestion.entering_question)
async def process_anon_question_text(message: Message, state: FSMContext):
    text = message.text.strip()
    if len(text) < 5:
        await message.answer("Пожалуйста, напиши более развернутый вопрос.")
        return
    await state.update_data(question_text=text)
    await state.set_state(StudentAnonQuestion.confirming)
    await message.answer(
        f"Твой вопрос:\n\n<i>{text}</i>\n\nОтправить?",
        parse_mode="HTML",
        reply_markup=get_question_confirm_keyboard(),
    )


@router.callback_query(StudentAnonQuestion.confirming, F.data == "question_confirm")
async def confirm_anon_question(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    text = data["question_text"]
    question_id = anon_repo.create(text, asker_user_id=callback.from_user.id)
    await state.clear()

    # Получаем имя и класс ученика
    user = user_repo.get_user(callback.from_user.id)
    student_info = f"{user['ФИ']}, {user['class']}" if user else "Аноним"

    # Кнопка "Ответить" ведёт прямо в обработчик ответа в admin_handlers
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Ответить", callback_data=f"question_answer:{question_id}")
    kb.button(text="🗑 Удалить", callback_data=f"question_delete:{question_id}")
    kb.adjust(2)

    notify_text = (
        f"❓ Новый вопрос от ученика\n"
        f"<b>От:</b> {student_info}\n\n"
        f"<i>{text}</i>"
    )

    admins = user_repo.get_all_admins()
    for admin_id, _ in admins:
        try:
            await bot.send_message(admin_id, notify_text, parse_mode="HTML", reply_markup=kb.as_markup())
        except Exception:
            pass

    await callback.message.edit_text("✅ Вопрос отправлен!", reply_markup=get_student_main_menu())


@router.callback_query(F.data == "question_cancel")
async def cancel_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text("Отменено.", reply_markup=get_student_main_menu())
