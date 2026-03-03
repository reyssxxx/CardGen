
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
    AdminGradeUpload, AdminCreateEvent, AdminAddSection,
    AdminSendAnnouncement, AdminAnswerQuestion, AdminSendCards,
)
from keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_class_selection_keyboard,
    get_grade_upload_action_keyboard,
    get_grade_confirm_keyboard,
    get_send_cards_keyboard,
    get_send_cards_confirm_keyboard,
    get_event_description_keyboard,
    get_admin_events_keyboard,
    get_event_manage_keyboard,
    get_event_manage_day_keyboard,
    get_section_skip_keyboard,
    get_section_capacity_keyboard,
    get_admin_section_detail_keyboard,
    get_announcement_audience_keyboard,
    get_announcement_confirm_keyboard,
    get_questions_keyboard,
    get_question_actions_keyboard,
    get_question_delete_confirm_keyboard,
    get_cancel_keyboard,
    get_stats_class_keyboard,
    get_event_delete_confirm_keyboard,
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
    await state.update_data(admin_id=callback.from_user.id)
    await state.set_state(AdminCreateEvent.entering_title)
    await callback.message.edit_text(
        "Создание дня мероприятий\n\nВведи название (например: «День словесности»):",
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
    await callback.message.edit_text("Вопросы от учеников:", reply_markup=get_questions_keyboard(questions))


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
    skipped_text = ""
    if result["skipped"]:
        skipped_names = ", ".join(result["skipped"][:5])
        more = f" и ещё {len(result['skipped']) - 5}" if len(result["skipped"]) > 5 else ""
        skipped_text = f"\n⚠️ Не найдены: {skipped_names}{more}"
    p_start = result["period_start"].strftime('%d.%m')
    p_end = result["period_end"].strftime('%d.%m.%Y')
    text = (
        f"✅ Файл обработан\n"
        f"Класс: <b>{class_name}</b> | Период: {p_start} — {p_end}\n"
        f"Оценок: <b>{result['count']}</b>"
        f"{skipped_text}\n\nСохранить?"
    )
    await wait.delete()
    await message.answer(text, parse_mode="HTML", reply_markup=get_grade_confirm_keyboard())


@router.message(AdminGradeUpload.waiting_for_file)
async def waiting_for_file_wrong_type(message: Message):
    await message.answer("Отправь файл формата .xlsx, а не текст или фото.")


@router.callback_query(AdminGradeUpload.confirming, F.data == "grade_confirm")
async def confirm_grades(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    result = data["parsed_result"]
    class_name = data["selected_class"]
    inserted = grade_repo.bulk_insert_grades(result["grades"])
    duplicates = result["count"] - inserted
    await state.clear()
    dup_text = f"\n⚠️ Пропущено дублей: {duplicates}" if duplicates else ""
    await callback.message.edit_text(
        f"✅ Оценки сохранены: {inserted} записей.{dup_text}",
        reply_markup=get_admin_main_menu(),
    )
    # Уведомить затронутых учеников
    if inserted > 0:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        student_names = {g["student_name"] for g in result["grades"]}
        students_in_class = user_repo.get_students_by_class(class_name)
        notify_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🎴 Мой табель", callback_data="menu:card")
        ]])
        for uid, name in students_in_class:
            if name in student_names:
                try:
                    await bot.send_message(
                        uid, "📊 Выставлены новые оценки! Проверь табель.",
                        reply_markup=notify_kb,
                    )
                except Exception:
                    pass
                await asyncio.sleep(0.05)


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


# ── Мероприятия: создание дня ─────────────────────────────────────────────────

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
        await message.answer("Неверный формат. Введи дату в формате ДД.ММ.ГГГГ (например: 15.03.2026)")
        return
    await state.update_data(event_date=date_str)
    await state.set_state(AdminCreateEvent.entering_description)
    await message.answer(
        "Описание дня (необязательно):",
        reply_markup=get_event_description_keyboard(),
    )


@router.message(AdminCreateEvent.entering_description)
async def event_enter_description(message: Message, state: FSMContext):
    await state.update_data(event_description=message.text.strip())
    await _create_event_day(message, state)


@router.callback_query(AdminCreateEvent.entering_description, F.data == "event_skip_desc")
async def event_skip_description(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(event_description=None)
    await _create_event_day(callback.message, state, edit=True)


async def _create_event_day(message, state: FSMContext, edit=False):
    """Создаёт день мероприятий в БД и показывает экран управления."""
    data = await state.get_data()
    event_id = event_repo.create_event(
        title=data["event_title"],
        date=data["event_date"],
        created_by=data.get("admin_id", 0),
        description=data.get("event_description"),
    )
    await state.update_data(event_id=event_id)
    await state.set_state(AdminCreateEvent.managing)
    await _show_event_manage(message, event_id, edit=edit)


async def _show_event_manage(message, event_id: int, edit=False):
    """Показать экран управления днём мероприятий."""
    event = event_repo.get_event(event_id)
    sections = event_repo.get_sections(event_id)
    desc = event.get("description") or ""
    published = bool(event.get("published"))
    pub_status = "🟢 Опубликовано" if published else "📝 Черновик"
    text = f"<b>📅 {event['title']}</b> — {event['date']}\n{pub_status}"
    if desc:
        text += f"\n\n{desc}"
    if sections:
        text += "\n\n<b>Секции:</b>"
        for i, s in enumerate(sections, 1):
            time_str = f"{s['time']} " if s.get('time') else ""
            host_str = f" — {s['host']}" if s.get('host') else ""
            cap_str = f" (лимит {s['capacity']})" if s.get('capacity') else ""
            text += f"\n{i}. {time_str}{s['title']}{host_str}{cap_str}"
    else:
        text += "\n\nСекций пока нет. Добавь первую секцию."
    kb = get_event_manage_day_keyboard(event_id, sections, published)
    if edit:
        await message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    else:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)


# ── Мероприятия: добавление секций ───────────────────────────────────────────

@router.callback_query(F.data.startswith("section_add:"))
async def section_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    await state.update_data(section_event_id=event_id)
    await state.set_state(AdminAddSection.entering_title)
    await callback.message.edit_text(
        "Название секции:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AdminAddSection.entering_title)
async def section_enter_title(message: Message, state: FSMContext):
    await state.update_data(section_title=message.text.strip())
    await state.set_state(AdminAddSection.entering_host)
    await message.answer(
        "Ведущий секции:",
        reply_markup=get_section_skip_keyboard("sec_skip_host"),
    )


@router.callback_query(AdminAddSection.entering_host, F.data == "sec_skip_host")
async def section_skip_host(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(section_host=None)
    await state.set_state(AdminAddSection.entering_time)
    await callback.message.edit_text(
        "Время секции (ЧЧ:ММ):",
        reply_markup=get_section_skip_keyboard("sec_skip_time"),
    )


@router.message(AdminAddSection.entering_host)
async def section_enter_host(message: Message, state: FSMContext):
    await state.update_data(section_host=message.text.strip())
    await state.set_state(AdminAddSection.entering_time)
    await message.answer(
        "Время секции (ЧЧ:ММ):",
        reply_markup=get_section_skip_keyboard("sec_skip_time"),
    )


@router.callback_query(AdminAddSection.entering_time, F.data == "sec_skip_time")
async def section_skip_time(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(section_time=None)
    await state.set_state(AdminAddSection.selecting_capacity)
    await callback.message.edit_text(
        "Лимит участников секции:",
        reply_markup=get_section_capacity_keyboard(),
    )


@router.message(AdminAddSection.entering_time)
async def section_enter_time(message: Message, state: FSMContext):
    from utils.validators import validate_time
    time_str = message.text.strip()
    if not validate_time(time_str):
        await message.answer("Неверный формат. Введи время в формате ЧЧ:ММ (например: 14:30)")
        return
    await state.update_data(section_time=time_str)
    await state.set_state(AdminAddSection.selecting_capacity)
    await message.answer(
        "Лимит участников секции:",
        reply_markup=get_section_capacity_keyboard(),
    )


@router.callback_query(AdminAddSection.selecting_capacity, F.data.startswith("sec_cap:"))
async def section_select_capacity(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    val = callback.data.split(":")[1]
    if val == "custom":
        await state.set_state(AdminAddSection.entering_custom_capacity)
        await callback.message.edit_text("Введи число:", reply_markup=get_cancel_keyboard())
        return
    cap = None if val == "0" else int(val)
    await state.update_data(section_capacity=cap)
    await state.set_state(AdminAddSection.entering_description)
    await callback.message.edit_text(
        "Описание секции (необязательно):",
        reply_markup=get_section_skip_keyboard("sec_skip_desc"),
    )


@router.message(AdminAddSection.entering_custom_capacity)
async def section_custom_capacity(message: Message, state: FSMContext):
    try:
        cap = int(message.text.strip())
        if cap <= 0:
            raise ValueError()
    except ValueError:
        await message.answer("Введи положительное число.")
        return
    await state.update_data(section_capacity=cap)
    await state.set_state(AdminAddSection.entering_description)
    await message.answer(
        "Описание секции (необязательно):",
        reply_markup=get_section_skip_keyboard("sec_skip_desc"),
    )


@router.callback_query(AdminAddSection.entering_description, F.data == "sec_skip_desc")
async def section_skip_desc(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(section_description=None)
    await _save_section(callback.message, state, edit=True)


@router.message(AdminAddSection.entering_description)
async def section_enter_desc(message: Message, state: FSMContext):
    await state.update_data(section_description=message.text.strip())
    await _save_section(message, state)


async def _save_section(message, state: FSMContext, edit=False):
    """Сохраняет секцию и возвращает к экрану управления днём."""
    data = await state.get_data()
    event_id = data["section_event_id"]
    event_repo.add_section(
        event_id=event_id,
        title=data["section_title"],
        host=data.get("section_host"),
        time=data.get("section_time"),
        description=data.get("section_description"),
        capacity=data.get("section_capacity"),
    )
    # Очистить данные секции, оставить event_id
    await state.set_state(AdminCreateEvent.managing)
    await state.update_data(event_id=event_id)
    await _show_event_manage(message, event_id, edit=edit)


# ── Мероприятия: управление секцией (просмотр/удаление) ──────────────────────

@router.callback_query(F.data.startswith("adm_section_view:"))
async def admin_view_section(callback: CallbackQuery):
    await callback.answer()
    section_id = int(callback.data.split(":")[1])
    section = event_repo.get_section(section_id)
    if not section:
        await callback.message.edit_text("Секция не найдена.", reply_markup=get_admin_main_menu())
        return
    regs = event_repo.get_section_registrations(section_id)
    count = len(regs)
    time_str = f"\n🕐 Время: {section['time']}" if section.get('time') else ""
    host_str = f"\n👤 Ведущий: {section['host']}" if section.get('host') else ""
    desc_str = f"\n\n{section['description']}" if section.get('description') else ""
    cap_str = f"\n👥 Записалось: {count}" + (f" из {section['capacity']}" if section.get('capacity') else "")
    text = f"<b>{section['title']}</b>{time_str}{host_str}{cap_str}{desc_str}"
    if regs:
        by_class = {}
        for r in regs:
            by_class.setdefault(r["class"], []).append(r["student_name"])
        text += "\n\n<b>Участники:</b>"
        for cls, names in sorted(by_class.items()):
            text += f"\n{cls}: " + ", ".join(names)
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=get_admin_section_detail_keyboard(section_id, section["event_id"]),
    )


@router.callback_query(F.data.startswith("section_delete:"))
async def delete_section(callback: CallbackQuery):
    await callback.answer()
    section_id = int(callback.data.split(":")[1])
    section = event_repo.get_section(section_id)
    if not section:
        await callback.message.edit_text("Секция не найдена.", reply_markup=get_admin_main_menu())
        return
    event_id = section["event_id"]
    event_repo.delete_section(section_id)
    await _show_event_manage(callback.message, event_id, edit=True)


# ── Мероприятия: публикация и уведомление ─────────────────────────────────────

@router.callback_query(F.data.startswith("event_publish:"))
async def publish_event(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    if not event:
        return
    sections = event_repo.get_sections(event_id)
    event_repo.publish_event(event_id)
    await state.clear()

    # Рассылка уведомлений
    students = user_repo.get_all_students()
    desc = event.get("description") or ""
    announce_text = f"📅 <b>Новое мероприятие!</b>\n<b>{event['title']}</b> — {event['date']}"
    if desc:
        announce_text += f"\n\n{desc}"
    if sections:
        announce_text += "\n\n<b>Секции:</b>"
        for s in sections:
            time_str = f"{s['time']} " if s.get('time') else ""
            announce_text += f"\n• {time_str}{s['title']}"

    from aiogram.utils.keyboard import InlineKeyboardBuilder as IKB
    notify_kb = IKB()
    notify_kb.button(text="📋 Подробнее и записаться", callback_data=f"event_view:{event_id}")
    notify_markup = notify_kb.as_markup()
    for uid, _, _ in students:
        try:
            await bot.send_message(uid, announce_text, parse_mode="HTML", reply_markup=notify_markup)
        except Exception:
            pass
        await asyncio.sleep(0.05)
    await callback.message.edit_text(
        f"✅ «{event['title']}» опубликовано! Уведомлено {len(students)} учеников.",
        reply_markup=get_admin_main_menu(),
    )


# ── Мероприятия: управление днём (из списка) и экран управления ───────────────

@router.callback_query(F.data.startswith("event_manage:"))
async def event_manage_from_list(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    await state.update_data(event_id=event_id)
    await state.set_state(AdminCreateEvent.managing)
    await _show_event_manage(callback.message, event_id, edit=True)


@router.callback_query(F.data.startswith("admin_event_view:"))
async def admin_view_event(callback: CallbackQuery):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    if not event:
        await callback.message.edit_text("Мероприятие не найдено.")
        return
    sections = event_repo.get_sections(event_id)
    has_sections = bool(sections)
    participants = event_repo.get_all_registrations(event_id)
    total = len(participants)
    text = f"<b>{event['title']}</b> — {event['date']}\nЗаписалось: <b>{total}</b>"
    pub = event.get("published", 1)
    if not pub:
        text += "\n📝 Черновик (не опубликовано)"
    if sections:
        text += "\n\n<b>Секции:</b>"
        for s in sections:
            count = event_repo.get_section_registration_count(s["id"])
            time_str = f"{s['time']} " if s.get('time') else ""
            cap_str = f" ({count}" + (f"/{s['capacity']}" if s.get('capacity') else "") + ")"
            text += f"\n• {time_str}{s['title']}{cap_str}"
    elif participants:
        text += "\n\n"
        by_class = {}
        for p in participants:
            by_class.setdefault(p["class"], []).append(p["student_name"])
        for cls, names in sorted(by_class.items()):
            text += f"<b>{cls}</b> ({len(names)} чел.):\n"
            text += ", ".join(names) + "\n\n"
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=get_event_manage_keyboard(event_id, bool(event.get("is_active")), has_sections),
    )


@router.callback_query(F.data.startswith("event_archive:"))
async def archive_event(callback: CallbackQuery):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event_repo.deactivate_event(event_id)
    await callback.message.edit_text("Мероприятие архивировано.", reply_markup=get_admin_main_menu())


@router.callback_query(F.data.startswith("event_delete_ask:"))
async def ask_delete_event(callback: CallbackQuery):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    name = event["title"] if event else f"#{event_id}"
    await callback.message.edit_text(
        f"Удалить «{name}» навсегда?\n\nВсе секции и записи участников будут уничтожены. Это действие нельзя отменить.",
        reply_markup=get_event_delete_confirm_keyboard(event_id),
    )


@router.callback_query(F.data.startswith("event_delete:"))
async def confirm_delete_event(callback: CallbackQuery):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    name = event["title"] if event else f"#{event_id}"
    event_repo.delete_event(event_id)
    await callback.message.edit_text(f"Мероприятие «{name}» удалено.", reply_markup=get_admin_main_menu())


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


# ── Вопросы учеников ─────────────────────────────────────────────────────────

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
    author = q.get("author_name") or "Неизвестный"
    author_class = q.get("author_class") or ""
    author_info = f"{author}, {author_class}" if author_class else author
    text = f"<b>От:</b> {author_info}\n<b>Дата:</b> {dt}\n\n<i>{q['text']}</i>"
    if q["answered"]:
        text += f"\n\n<b>Ответ:</b>\n{q['answer']}"
    kb = get_question_actions_keyboard(q_id, bool(q["answered"]))
    question_photo = q.get("photo_file_id")
    answer_photo = q.get("answer_photo_file_id")
    # If there's a question photo, delete current message and send photo instead
    if question_photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(question_photo, caption=text, parse_mode="HTML", reply_markup=kb)
        if answer_photo and q["answered"]:
            await callback.message.answer_photo(answer_photo, caption="📷 Фото к ответу")
    else:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        if answer_photo and q["answered"]:
            await callback.message.answer_photo(answer_photo, caption="📷 Фото к ответу")


@router.callback_query(F.data.startswith("question_answer:"))
async def start_answer_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    q_id = int(callback.data.split(":")[1])
    q = anon_repo.get_by_id(q_id)
    await state.update_data(answering_question_id=q_id)
    await state.set_state(AdminAnswerQuestion.entering_answer)
    question_text = f"\n\n<i>{q['text']}</i>" if q else ""
    prompt = f"<b>Введи ответ на вопрос:</b>{question_text}\n\nМожно отправить текст или фото с подписью."
    question_photo = q.get("photo_file_id") if q else None
    if question_photo:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(question_photo, caption=prompt, parse_mode="HTML", reply_markup=get_cancel_keyboard())
    else:
        await callback.message.edit_text(prompt, parse_mode="HTML", reply_markup=get_cancel_keyboard())


@router.message(AdminAnswerQuestion.entering_answer, F.photo)
async def answer_enter_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    q_id = data["answering_question_id"]
    photo_id = message.photo[-1].file_id
    answer = message.caption.strip() if message.caption else ""
    q = anon_repo.get_by_id(q_id)
    anon_repo.answer(q_id, answer, answer_photo_file_id=photo_id)
    send_text = f"💬 Ответ на твой вопрос:\n\n<i>{q['text']}</i>"
    if answer:
        send_text += f"\n\n{answer}"
    sent = 0
    asker_id = q.get("asker_user_id")
    if asker_id:
        try:
            await bot.send_photo(asker_id, photo_id, caption=send_text, parse_mode="HTML")
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


@router.message(AdminAnswerQuestion.entering_answer, F.text)
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


@router.message(AdminAnswerQuestion.entering_answer)
async def answer_wrong_type(message: Message):
    await message.answer("Отправь текст или фото с подписью.")


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
    await callback.message.edit_text("Вопросы от учеников:", reply_markup=get_questions_keyboard(questions))


# ── Экспорт участников мероприятия ────────────────────────────────────────────

@router.callback_query(F.data.startswith("event_export:"))
async def export_event_participants(callback: CallbackQuery):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    if not event:
        await callback.message.edit_text("Мероприятие не найдено.")
        return

    sections = event_repo.get_sections(event_id)
    total = event_repo.get_total_registrations(event_id)
    lines = [f"Мероприятие: {event['title']}", f"Дата: {event['date']}", f"Всего участников: {total}", ""]

    if sections:
        for s in sections:
            regs = event_repo.get_section_registrations(s["id"])
            time_str = f"{s['time']} " if s.get('time') else ""
            host_str = f" ({s['host']})" if s.get('host') else ""
            lines.append(f"=== {time_str}{s['title']}{host_str} ({len(regs)} чел.) ===")
            for p in regs:
                lines.append(f"  {p['student_name']} ({p['class']})")
            lines.append("")
    else:
        regs = event_repo.get_registrations_by_event(event_id)
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


# ── Просмотр оценок по классу ────────────────────────────────────────────────

@router.callback_query(F.data == "menu:view_grades")
async def menu_view_grades(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    classes = get_all_classes()
    await callback.message.edit_text(
        "Выбери класс для просмотра оценок:",
        reply_markup=get_class_selection_keyboard(classes, "view_grades_class"),
    )


@router.callback_query(F.data.startswith("view_grades_class:"))
async def view_grades_class(callback: CallbackQuery):
    await callback.answer()
    class_name = callback.data.split(":", 1)[1]
    grades = grade_repo.get_grades_by_class(class_name)
    if not grades:
        await callback.message.edit_text(
            f"Оценок для класса <b>{class_name}</b> пока нет.",
            parse_mode="HTML", reply_markup=get_admin_main_menu(),
        )
        return
    recent = grades[:30]
    lines = []
    for g in recent:
        lines.append(f"  {g['date']}  {g['student_name']}: {g['subject']} — <b>{g['grade']}</b>")
    text = f"<b>Оценки класса {class_name}</b> (последние {len(recent)}):\n\n" + "\n".join(lines)
    if len(grades) > 30:
        text += f"\n\n... и ещё {len(grades) - 30}"
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_admin_main_menu())
