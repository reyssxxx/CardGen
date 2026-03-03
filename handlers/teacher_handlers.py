"""
Handlers для функционала учителя.

Учитель определяется по Telegram ID в data/teachers.json.
Возможности:
  - Рассылка объявлений своим классам
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.user_repository import UserRepository
from database.announcement_repository import AnnouncementRepository
from handlers.states import TeacherSendAnnouncement
from keyboards.teacher_keyboards import (
    get_teacher_main_menu,
    get_teacher_class_keyboard,
    get_teacher_announcement_confirm_keyboard,
)
from keyboards.common_keyboards import get_cancel_keyboard
from services.mailing_service import MailingService
from utils.config_loader import get_teacher_classes, get_teacher_name, get_students_by_class

router = Router()

user_repo = UserRepository()
announce_repo = AnnouncementRepository()


def _get_teacher(user_id: int) -> dict | None:
    """Вернуть пользователя, если он учитель."""
    user = user_repo.get_user(user_id)
    if not user or not user["isTeacher"]:
        return None
    return user


# ── Отмена / Назад ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "teacher_cancel")
async def teacher_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.edit_text("Главное меню:", reply_markup=get_teacher_main_menu())


# ── Мои классы ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "teacher:my_classes")
async def teacher_my_classes(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if not _get_teacher(user_id):
        return
    classes = get_teacher_classes(user_id)
    if not classes:
        await callback.message.edit_text(
            "У тебя нет привязанных классов. Обратись к администратору.",
            reply_markup=get_teacher_main_menu(),
        )
        return
    text = "<b>Твои классы:</b>\n\n"
    for cls in classes:
        students = get_students_by_class(cls)
        text += f"<b>{cls}</b> ({len(students)} уч.):\n"
        text += ", ".join(students) + "\n\n"
    await callback.message.edit_text(text.strip(), parse_mode="HTML", reply_markup=get_teacher_main_menu())


# ── История рассылок ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "teacher:history")
async def teacher_history(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if not _get_teacher(user_id):
        return
    announcements = announce_repo.get_by_teacher(user_id, limit=10)
    if not announcements:
        await callback.message.edit_text(
            "Ты ещё не отправлял объявлений.",
            reply_markup=get_teacher_main_menu(),
        )
        return
    from datetime import datetime
    text = "<b>История рассылок (последние 10):</b>\n\n"
    for ann in announcements:
        dt = datetime.fromisoformat(ann["created_at"]).strftime("%d.%m.%Y")
        target = ann["target"]
        short = ann["text"][:100] + ("..." if len(ann["text"]) > 100 else "")
        text += f"<b>{dt} → {target}</b>\n{short}\n\n"
    await callback.message.edit_text(text.strip(), parse_mode="HTML", reply_markup=get_teacher_main_menu())


# ── Объявления ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "teacher:announce")
async def teacher_announce(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    if not _get_teacher(user_id):
        return
    classes = get_teacher_classes(user_id)
    if not classes:
        await callback.message.edit_text(
            "У тебя нет привязанных классов. Обратись к администратору.",
            reply_markup=get_teacher_main_menu(),
        )
        return
    await state.set_state(TeacherSendAnnouncement.selecting_class)
    await callback.message.edit_text(
        "Выбери класс для объявления:",
        reply_markup=get_teacher_class_keyboard(classes, "teacher_ann_class"),
    )


@router.callback_query(TeacherSendAnnouncement.selecting_class, F.data.startswith("teacher_ann_class:"))
async def announce_select_class(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    class_name = callback.data.split(":", 1)[1]
    await state.update_data(announce_class=class_name)
    await state.set_state(TeacherSendAnnouncement.entering_text)
    await callback.message.edit_text(
        f"Класс: <b>{class_name}</b>\n\nОтправь текст или фото с подписью:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard("teacher_cancel"),
    )


@router.message(TeacherSendAnnouncement.entering_text, F.photo)
async def teacher_announce_receive_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    caption = message.caption or ""
    await state.update_data(announce_photo=file_id, announce_text=caption)
    data = await state.get_data()
    await state.set_state(TeacherSendAnnouncement.confirming)
    await message.answer_photo(
        file_id,
        caption=f"Отправить в <b>{data['announce_class']}</b>?\n\n<b>Подпись:</b> {caption or '(нет)'}",
        parse_mode="HTML",
        reply_markup=get_teacher_announcement_confirm_keyboard(),
    )


@router.message(TeacherSendAnnouncement.entering_text, F.text)
async def announce_enter_text(message: Message, state: FSMContext):
    await state.update_data(announce_text=message.text.strip(), announce_photo=None)
    data = await state.get_data()
    await state.set_state(TeacherSendAnnouncement.confirming)
    await message.answer(
        f"Отправить объявление в <b>{data['announce_class']}</b>?\n\n"
        f"<b>Текст:</b>\n{message.text}",
        parse_mode="HTML",
        reply_markup=get_teacher_announcement_confirm_keyboard(),
    )


@router.callback_query(TeacherSendAnnouncement.confirming, F.data == "teacher_announce_confirm")
async def announce_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    text = data["announce_text"]
    class_name = data["announce_class"]
    photo_file_id = data.get("announce_photo")
    user_id = callback.from_user.id

    teacher_name = get_teacher_name(user_id) or "Учитель"
    announce_repo.create(text, user_id, class_name, photo_file_id=photo_file_id)

    recipients = user_repo.get_students_by_class(class_name)
    send_text = f"📢 Объявление от {teacher_name}:\n\n{text}" if text else f"📢 Объявление от {teacher_name}:"
    mailing = MailingService(bot)
    sent, failed = await mailing.send_text_to_users(recipients, send_text, photo_file_id=photo_file_id)

    await state.clear()
    result_text = f"✅ Объявление отправлено. Доставлено: {sent}. Ошибок: {failed}."
    if photo_file_id:
        await callback.message.edit_caption(caption=result_text, reply_markup=get_teacher_main_menu())
    else:
        await callback.message.edit_text(result_text, reply_markup=get_teacher_main_menu())
