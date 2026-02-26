
"""
Обработчики команд администратора.
"""
import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile, BufferedInputFile
from aiogram.fsm.context import FSMContext

from database.user_repository import UserRepository
from database.grade_repository import GradeRepository
from database.event_repository import EventRepository
from database.announcement_repository import AnnouncementRepository
from database.anon_question_repository import AnonQuestionRepository
from handlers.states import (
    AdminGradeUpload, AdminCreateEvent, AdminSendAnnouncement,
    AdminAnswerQuestion, AdminSendCards,
)
from keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_class_selection_keyboard,
    get_grade_upload_action_keyboard,
    get_grade_confirm_keyboard,
    get_send_cards_keyboard,
    get_send_cards_confirm_keyboard,
    get_event_limit_keyboard,
    get_event_description_keyboard,
    get_event_confirm_keyboard,
    get_admin_events_keyboard,
    get_event_manage_keyboard,
    get_announcement_audience_keyboard,
    get_announcement_confirm_keyboard,
    get_questions_keyboard,
    get_question_actions_keyboard,
    get_question_delete_confirm_keyboard,
    get_cancel_keyboard,
    get_stats_class_keyboard,
    get_mailing_confirm_keyboard,
)
from services.mailing_service import MailingService
from services.excel_import_service import parse_grades_excel, generate_template_excel
from utils.config_loader import get_all_classes, get_students_by_class, get_subjects

router = Router()
user_repo = UserRepository()
grade_repo = GradeRepository()
event_repo = EventRepository()
announce_repo = AnnouncementRepository()
anon_repo = AnonQuestionRepository()


def _is_admin(user_id: int) -> bool:
    return user_repo.is_admin(user_id)


# ── Отмена ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text("Главное меню:", reply_markup=get_admin_main_menu())


# ── Меню администратора (инлайн-кнопки) ───────────────────────────────────────

@router.callback_query(F.data == "menu:grades")
async def menu_grades(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    classes = get_all_classes()
    await state.set_state(AdminGradeUpload.selecting_class)
    await callback.message.edit_text(
        "Выбери класс для загрузки оценок:",
        reply_markup=get_class_selection_keyboard(classes, "grade_class"),
    )


@router.callback_query(F.data == "menu:send_cards")
async def menu_send_cards(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    classes = get_all_classes()
    await state.set_state(AdminSendCards.selecting_class)
    await callback.message.edit_text(
        "Кому разослать табели?",
        reply_markup=get_send_cards_keyboard(classes),
    )


@router.callback_query(F.data == "menu:create_event")
async def menu_create_event(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminCreateEvent.entering_title)
    await callback.message.edit_text(
        "Создание мероприятия\n\nВведи название:",
        reply_markup=get_cancel_keyboard(),
    )


@router.callback_query(F.data == "menu:events_admin")
async def menu_events_admin(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    events = event_repo.get_all_events()
    if not events:
        await callback.message.edit_text("Мероприятий пока нет.", reply_markup=get_admin_main_menu())
        return
    await callback.message.edit_text("Мероприятия:", reply_markup=get_admin_events_keyboard(events))


@router.callback_query(F.data == "menu:announce")
async def menu_announce(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    classes = get_all_classes()
    await state.set_state(AdminSendAnnouncement.selecting_audience)
    await callback.message.edit_text(
        "Кому отправить объявление?",
        reply_markup=get_announcement_audience_keyboard(classes),
    )


@router.callback_query(F.data == "menu:questions")
async def menu_questions(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    questions = anon_repo.get_all()
    if not questions:
        await callback.message.edit_text("Вопросов пока нет.", reply_markup=get_admin_main_menu())
        return
    await callback.message.edit_text("Анонимные вопросы:", reply_markup=get_questions_keyboard(questions))


@router.callback_query(F.data == "menu:students")
async def menu_students(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
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


# ── Оценки: загрузка Excel ────────────────────────────────────────────────────

@router.callback_query(AdminGradeUpload.selecting_class, F.data.startswith("grade_class:"))
async def grade_select_class(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    class_name = callback.data.split(":", 1)[1]
    await state.update_data(selected_class=class_name)
    await state.set_state(AdminGradeUpload.selecting_action)
    await callback.message.edit_text(
        f"Класс: <b>{class_name}</b>\n\nЧто делаем?",
        parse_mode="HTML",
        reply_markup=get_grade_upload_action_keyboard(),
    )


@router.callback_query(AdminGradeUpload.selecting_action, F.data == "grade_download_template")
async def download_template(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    class_name = data["selected_class"]
    students = get_students_by_class(class_name)
    subjects = get_subjects()
    xlsx_bytes = generate_template_excel(class_name, students, subjects)
    file = BufferedInputFile(xlsx_bytes, filename=f"шаблон_{class_name}.xlsx")
    await callback.message.answer_document(file, caption=f"Шаблон для класса {class_name}")
    await state.clear()
    await callback.message.edit_text("Главное меню:", reply_markup=get_admin_main_menu())


@router.callback_query(AdminGradeUpload.selecting_action, F.data == "grade_upload_file")
async def ask_for_excel_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminGradeUpload.waiting_for_file)
    await callback.message.edit_text(
        "Отправь .xlsx файл с оценками:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AdminGradeUpload.waiting_for_file, F.document)
async def process_excel_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.endswith(".xlsx"):
        await message.answer("Отправь файл формата .xlsx")
        return
    data = await state.get_data()
    class_name = data["selected_class"]
    students = get_students_by_class(class_name)
    wait = await message.answer("Обрабатываю файл...")
    file_path = f"data/uploaded_grades/{class_name}_{doc.file_id}.xlsx"
    os.makedirs("data/uploaded_grades", exist_ok=True)
    await bot.download(doc, destination=file_path)
    try:
        result = parse_grades_excel(file_path, class_name, students)
    except Exception as e:
        await wait.delete()
        await message.answer(f"Ошибка при обработке файла:\n{e}")
        return
    await state.update_data(parsed_result=result, file_path=file_path)
    await state.set_state(AdminGradeUpload.confirming)
    dates = result["dates"]
    period_str = f"{dates[0].strftime('%d.%m')} — {dates[-1].strftime('%d.%m.%Y')}" if dates else "неизвестно"
    skipped_text = ""
    if result["skipped"]:
        skipped_names = ", ".join(result["skipped"][:5])
        more = f" и ещё {len(result['skipped']) - 5}" if len(result["skipped"]) > 5 else ""
        skipped_text = f"\n⚠️ Не найдены: {skipped_names}{more}"
    text = (
        f"✅ Файл обработан\n"
        f"Класс: <b>{class_name}</b> | Период: {period_str}\n"
        f"Оценок: <b>{result['count']}</b>"
        f"{skipped_text}\n\nСохранить?"
    )
    await wait.delete()
    await message.answer(text, parse_mode="HTML", reply_markup=get_grade_confirm_keyboard())


@router.callback_query(AdminGradeUpload.confirming, F.data == "grade_confirm")
async def confirm_grades(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    result = data["parsed_result"]
    inserted = grade_repo.bulk_insert_grades(result["grades"])
    duplicates = result["count"] - inserted
    await state.clear()
    dup_text = f"\n⚠️ Пропущено дублей: {duplicates}" if duplicates else ""
    await callback.message.edit_text(
        f"✅ Оценки сохранены: {inserted} записей.{dup_text}",
        reply_markup=get_admin_main_menu(),
    )


# ── Рассылка табелей ──────────────────────────────────────────────────────────

@router.callback_query(AdminSendCards.selecting_class, F.data.startswith("cards_class:"))
async def cards_select_class(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    target = callback.data.split(":", 1)[1]
    if target == "all":
        students = user_repo.get_all_students()
    else:
        students = user_repo.get_students_by_class(target)
    count = len(students)
    await state.update_data(cards_target=target, cards_count=count)
    await state.set_state(AdminSendCards.confirming)
    label = "всем" if target == "all" else f"классу {target}"
    await callback.message.edit_text(
        f"Разослать табели {label}: <b>{count}</b> учеников?",
        parse_mode="HTML",
        reply_markup=get_send_cards_confirm_keyboard(target, count),
    )


@router.callback_query(AdminSendCards.confirming, F.data.startswith("cards_confirm:"))
async def confirm_send_cards(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    target = data["cards_target"]
    await state.clear()
    if target == "all":
        students_raw = user_repo.get_all_students()
    else:
        all_s = user_repo.get_all_students()
        students_raw = [(uid, name, cls) for uid, name, cls in all_s if cls == target]
    students = [(uid, name, cls) for uid, name, cls in students_raw]
    progress_msg = await callback.message.edit_text(f"Начинаю рассылку... 0/{len(students)}")
    last_update = [0]

    async def on_progress(done, total):
        if done - last_update[0] >= 5 or done == total:
            last_update[0] = done
            try:
                await progress_msg.edit_text(f"📤 Отправлено: {done}/{total}")
            except Exception:
                pass

    mailing = MailingService(bot)
    sent, failed = await mailing.send_grade_cards(students, on_progress)
    await progress_msg.edit_text(
        f"✅ Рассылка завершена.\nОтправлено: {sent}. Ошибок: {failed}.",
        reply_markup=get_admin_main_menu(),
    )


# ── Мероприятия ───────────────────────────────────────────────────────────────

@router.message(AdminCreateEvent.entering_title)
async def event_enter_title(message: Message, state: FSMContext):
    await state.update_data(event_title=message.text.strip())
    await state.set_state(AdminCreateEvent.entering_date)
    await message.answer(
        "Дата мероприятия (ДД.ММ.ГГГГ):",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AdminCreateEvent.entering_date)
async def event_enter_date(message: Message, state: FSMContext):
    from utils.validators import validate_date
    date_str = message.text.strip()
    if not validate_date(date_str):
        await message.answer("Неверный формат. Введи дату в формате ДД.ММ.ГГГГ (например: 15.03.2025)")
        return
    await state.update_data(event_date=date_str)
    await state.set_state(AdminCreateEvent.selecting_limit)
    await message.answer(
        "Лимит участников от класса:",
        reply_markup=get_event_limit_keyboard(),
    )


@router.callback_query(AdminCreateEvent.selecting_limit, F.data.startswith("event_limit:"))
async def event_select_limit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    val = callback.data.split(":")[1]
    if val == "custom":
        await state.set_state(AdminCreateEvent.entering_custom_limit)
        await callback.message.edit_text("Введи количество человек:", reply_markup=get_cancel_keyboard())
        return
    limit = None if val == "0" else int(val)
    await state.update_data(event_limit=limit)
    await state.set_state(AdminCreateEvent.entering_description)
    await callback.message.edit_text(
        "Описание (необязательно):",
        reply_markup=get_event_description_keyboard(),
    )


@router.message(AdminCreateEvent.entering_custom_limit)
async def event_custom_limit(message: Message, state: FSMContext):
    try:
        limit = int(message.text.strip())
        if limit <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Введи положительное число.")
        return
    await state.update_data(event_limit=limit)
    await state.set_state(AdminCreateEvent.entering_description)
    await message.answer("Описание (необязательно):", reply_markup=get_event_description_keyboard())


@router.message(AdminCreateEvent.entering_description)
async def event_enter_description(message: Message, state: FSMContext):
    await state.update_data(event_description=message.text.strip())
    await show_event_preview(message, state)


@router.callback_query(AdminCreateEvent.entering_description, F.data == "event_skip_desc")
async def event_skip_description(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(event_description=None)
    await show_event_preview(callback.message, state, edit=True)


async def show_event_preview(message, state: FSMContext, edit=False):
    data = await state.get_data()
    limit_text = f"Лимит: {data['event_limit']} чел/класс" if data.get("event_limit") else "Без лимита"
    desc = data.get("event_description") or ""
    text = (
        f"<b>{data['event_title']}</b>\n"
        f"Дата: {data['event_date']}\n"
        f"{limit_text}"
        + (f"\n\n{desc}" if desc else "")
        + "\n\nСоздать мероприятие?"
    )
    await state.set_state(AdminCreateEvent.confirming)
    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=get_event_confirm_keyboard())
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=get_event_confirm_keyboard())


@router.callback_query(AdminCreateEvent.confirming, F.data == "event_confirm")
async def confirm_create_event(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    event_repo.create_event(
        title=data["event_title"],
        date=data["event_date"],
        time_slots=[""],
        created_by=callback.from_user.id,
        class_limit=data.get("event_limit"),
        description=data.get("event_description"),
    )
    await state.clear()
    students = user_repo.get_all_students()
    announce_text = f"📅 Новое мероприятие: <b>{data['event_title']}</b> — {data['event_date']}\nЗарегистрируйся в боте!"
    for uid, _, _ in students:
        try:
            await bot.send_message(uid, announce_text, parse_mode="HTML")
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await callback.message.edit_text(
        f"✅ Мероприятие «{data['event_title']}» создано! Уведомлено {len(students)} учеников.",
        reply_markup=get_admin_main_menu(),
    )


@router.callback_query(F.data.startswith("admin_event_view:"))
async def admin_view_event(callback: CallbackQuery):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    if not event:
        await callback.message.edit_text("Мероприятие не найдено.")
        return
    participants = event_repo.get_all_registrations(event_id)
    total = len(participants)
    text = f"<b>{event['title']}</b> — {event['date']}\nЗаписалось: <b>{total}</b>\n\n"
    if participants:
        by_class = {}
        for p in participants:
            by_class.setdefault(p["class"], []).append(p["student_name"])
        for cls, names in sorted(by_class.items()):
            text += f"<b>{cls}</b> ({len(names)} чел.):\n"
            text += ", ".join(names) + "\n\n"
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=get_event_manage_keyboard(event_id, bool(event.get("is_active"))),
    )


@router.callback_query(F.data.startswith("event_archive:"))
async def archive_event(callback: CallbackQuery):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event_repo.deactivate_event(event_id)
    await callback.message.edit_text("Мероприятие архивировано.", reply_markup=get_admin_main_menu())


@router.callback_query(F.data == "admin_events_back")
async def back_to_events_list(callback: CallbackQuery):
    await callback.answer()
    events = event_repo.get_all_events()
    if not events:
        await callback.message.edit_text("Мероприятий нет.", reply_markup=get_admin_main_menu())
        return
    await callback.message.edit_text("Мероприятия:", reply_markup=get_admin_events_keyboard(events))


# ── Объявления ────────────────────────────────────────────────────────────────

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
    announce_repo.create(text, callback.from_user.id, target)
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


# ── Анонимные вопросы ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("question_view:"))
async def admin_view_question(callback: CallbackQuery):
    await callback.answer()
    q_id = int(callback.data.split(":")[1])
    q = anon_repo.get_by_id(q_id)
    if not q:
        await callback.message.edit_text("Вопрос не найден.")
        return
    from datetime import datetime
    dt = datetime.fromisoformat(q["created_at"]).strftime("%d.%m.%Y %H:%M")
    text = f"<i>{q['text']}</i>\n\n{dt}"
    if q["answered"]:
        text += f"\n\nОтвет: {q['answer']}"
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=get_question_actions_keyboard(q_id, bool(q["answered"])),
    )


@router.callback_query(F.data.startswith("question_answer:"))
async def start_answer_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    q_id = int(callback.data.split(":")[1])
    await state.update_data(answering_question_id=q_id)
    await state.set_state(AdminAnswerQuestion.entering_answer)
    await callback.message.edit_text(
        "Введи ответ на вопрос:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AdminAnswerQuestion.entering_answer)
async def answer_enter_text(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    q_id = data["answering_question_id"]
    answer = message.text.strip()
    q = anon_repo.get_by_id(q_id)
    anon_repo.answer(q_id, answer)
    send_text = f"💬 Ответ на твой вопрос:\n\n<i>{q['text']}</i>\n\n{answer}"
    sent = 0
    asker_id = q.get("asker_user_id")
    if asker_id:
        try:
            await bot.send_message(asker_id, send_text, parse_mode="HTML")
            sent = 1
        except Exception:
            pass
    await state.clear()
    result = (
        "✅ Ответ отправлен автору вопроса."
        if sent
        else "✅ Ответ сохранён (не удалось доставить — пользователь мог заблокировать бота)."
    )
    await message.answer(result, reply_markup=get_admin_main_menu())


@router.callback_query(F.data.startswith("question_delete_ask:"))
async def ask_delete_question(callback: CallbackQuery):
    """Запрос подтверждения перед удалением вопроса."""
    await callback.answer()
    q_id = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "Удалить этот вопрос? Это действие нельзя отменить.",
        reply_markup=get_question_delete_confirm_keyboard(q_id),
    )


@router.callback_query(F.data.startswith("question_delete:"))
async def delete_question(callback: CallbackQuery):
    await callback.answer()
    q_id = int(callback.data.split(":")[1])
    anon_repo.delete(q_id)
    await callback.message.edit_text("Вопрос удалён.", reply_markup=get_admin_main_menu())


@router.callback_query(F.data == "questions_back")
async def back_to_questions(callback: CallbackQuery):
    await callback.answer()
    questions = anon_repo.get_all()
    if not questions:
        await callback.message.edit_text("Вопросов пока нет.", reply_markup=get_admin_main_menu())
        return
    await callback.message.edit_text("Анонимные вопросы:", reply_markup=get_questions_keyboard(questions))


# ── Экспорт участников мероприятия ────────────────────────────────────────────

@router.callback_query(F.data.startswith("event_export:"))
async def export_event_participants(callback: CallbackQuery):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    if not event:
        await callback.message.edit_text("Мероприятие не найдено.")
        return
    regs = event_repo.get_registrations_by_event(event_id)
    total = event_repo.get_total_registrations(event_id)

    lines = [f"Мероприятие: {event['title']}", f"Дата: {event['date']}", f"Всего участников: {total}", ""]
    for slot in event["time_slots"]:
        participants = regs.get(slot, [])
        lines.append(f"=== {slot} ({len(participants)} чел.) ===")
        for p in participants:
            lines.append(f"  {p['student_name']} ({p['class']})")
        lines.append("")

    text_content = "\n".join(lines)
    file = BufferedInputFile(
        text_content.encode("utf-8"),
        filename=f"участники_{event['title']}_{event['date']}.txt",
    )
    await callback.message.answer_document(
        file,
        caption=f"Список участников: {event['title']}",
    )


# ── Статистика по классу ───────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:stats")
async def menu_stats(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
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
    dist_lines = []
    for g in ("5", "4", "3", "2"):
        cnt = counts.get(g, 0)
        if cnt:
            dist_lines.append(f"  «{g}» — {cnt} шт.")

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


# ── Ручная рассылка табелей ───────────────────────────────────────────────────

@router.callback_query(F.data == "menu:mailing_now")
async def menu_mailing_now(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    count = len(user_repo.get_all_students())
    await callback.message.edit_text(
        f"Разослать табели всем <b>{count}</b> ученикам прямо сейчас?",
        parse_mode="HTML",
        reply_markup=get_mailing_confirm_keyboard(),
    )


@router.callback_query(F.data == "mailing_now_confirm")
async def mailing_now_confirm(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    students = user_repo.get_all_students()
    progress_msg = await callback.message.edit_text(f"Начинаю рассылку... 0/{len(students)}")
    last_update = [0]

    async def on_progress(done, total):
        if done - last_update[0] >= 5 or done == total:
            last_update[0] = done
            try:
                await progress_msg.edit_text(f"📤 Отправлено: {done}/{total}")
            except Exception:
                pass

    mailing = MailingService(bot)
    sent, failed = await mailing.send_grade_cards(students, on_progress)
    await progress_msg.edit_text(
        f"✅ Рассылка завершена.\nОтправлено: {sent}. Ошибок: {failed}.",
        reply_markup=get_admin_main_menu(),
    )
