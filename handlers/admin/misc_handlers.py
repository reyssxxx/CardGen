"""
Хендлеры администратора: объявления, вопросы, статистика, ученики, рассылка.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from handlers.admin.common import is_admin, user_repo, grade_repo, announce_repo, anon_repo
from handlers.states import AdminSendAnnouncement, AdminAnswerQuestion
from keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_class_selection_keyboard,
    get_announcement_audience_keyboard,
    get_announcement_confirm_keyboard,
    get_questions_keyboard,
    get_question_actions_keyboard,
    get_question_delete_confirm_keyboard,
    get_stats_class_keyboard,
    get_mailing_confirm_keyboard,
    get_cancel_keyboard,
)
from services.mailing_service import MailingService
from utils.config_loader import get_all_classes
from utils.pagination import paginate

router = Router()


def _questions_page_markup(questions, page):
    page_items, has_prev, has_next = paginate(questions, page)
    return get_questions_keyboard(page_items, page=page, has_prev=has_prev, has_next=has_next)


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

def _questions_header() -> str:
    stats = anon_repo.get_stats()
    return (
        f"❓ <b>Анонимные вопросы</b>\n"
        f"Всего: {stats['total']} | "
        f"Без ответа: {stats['unanswered']} | "
        f"Отвечено: {stats['answered']}"
    )


@router.callback_query(F.data == "menu:questions")
async def menu_questions(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    questions = anon_repo.get_all()
    header = _questions_header()
    if not questions:
        await callback.message.edit_text(header + "\n\nВопросов пока нет.", parse_mode="HTML", reply_markup=get_admin_main_menu())
        return
    await callback.message.edit_text(header, parse_mode="HTML", reply_markup=_questions_page_markup(questions, 0))


@router.callback_query(F.data.startswith("questions_page:"))
async def questions_paginate(callback: CallbackQuery):
    await callback.answer()
    page = int(callback.data.split(":")[1])
    questions = anon_repo.get_all()
    header = _questions_header()
    if not questions:
        await callback.message.edit_text(header + "\n\nВопросов пока нет.", parse_mode="HTML", reply_markup=get_admin_main_menu())
        return
    await callback.message.edit_text(header, parse_mode="HTML", reply_markup=_questions_page_markup(questions, page))


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
    await callback.message.edit_text("Введи ответ на вопрос:", reply_markup=get_cancel_keyboard())


@router.message(AdminAnswerQuestion.entering_answer)
async def answer_enter_text(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    q_id = data["answering_question_id"]
    answer = message.text.strip()
    q = anon_repo.get_by_id(q_id)
    anon_repo.answer(q_id, answer)
    send_text = f"💬 Ответ на твой вопрос:\n\n<i>{q['text']}</i>\n\n{answer}"
    asker_id = q.get("asker_user_id")
    await state.clear()
    if not asker_id:
        result = "✅ Ответ сохранён. Автор вопроса не идентифицирован (вопрос создан до обновления системы)."
    else:
        try:
            await bot.send_message(asker_id, send_text, parse_mode="HTML")
            result = "✅ Ответ отправлен автору вопроса."
        except Exception:
            result = "✅ Ответ сохранён (не удалось доставить — пользователь мог заблокировать бота)."
    await message.answer(result, reply_markup=get_admin_main_menu())


@router.callback_query(F.data.startswith("question_delete_ask:"))
async def ask_delete_question(callback: CallbackQuery):
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
    header = _questions_header()
    if not questions:
        await callback.message.edit_text(header + "\n\nВопросов пока нет.", parse_mode="HTML", reply_markup=get_admin_main_menu())
        return
    await callback.message.edit_text(header, parse_mode="HTML", reply_markup=_questions_page_markup(questions, 0))


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


# ── Ручная рассылка табелей ───────────────────────────────────────────────────

@router.callback_query(F.data == "menu:mailing_now")
async def menu_mailing_now(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
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
