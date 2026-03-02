"""
Хендлеры администратора: создание и управление мероприятиями.
"""
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from handlers.admin.common import is_admin, user_repo, event_repo
from handlers.states import AdminCreateEvent
from keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_event_limit_keyboard,
    get_event_description_keyboard,
    get_event_confirm_keyboard,
    get_admin_events_keyboard,
    get_event_manage_keyboard,
    get_cancel_keyboard,
)
from utils.pagination import paginate

router = Router()


def _events_page_markup(events, page):
    page_items, has_prev, has_next = paginate(events, page)
    return get_admin_events_keyboard(page_items, page=page, has_prev=has_prev, has_next=has_next)


# ── Создание мероприятия ──────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:create_event")
async def menu_create_event(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminCreateEvent.entering_title)
    await callback.message.edit_text(
        "Создание мероприятия\n\nВведи название:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AdminCreateEvent.entering_title)
async def event_enter_title(message: Message, state: FSMContext):
    await state.update_data(event_title=message.text.strip())
    await state.set_state(AdminCreateEvent.entering_date)
    await message.answer("Дата мероприятия (ДД.ММ.ГГГГ):", reply_markup=get_cancel_keyboard())


@router.message(AdminCreateEvent.entering_date)
async def event_enter_date(message: Message, state: FSMContext):
    from utils.validators import validate_date
    date_str = message.text.strip()
    if not validate_date(date_str):
        await message.answer("Неверный формат. Введи дату в формате ДД.ММ.ГГГГ (например: 15.03.2025)")
        return
    await state.update_data(event_date=date_str)
    await state.set_state(AdminCreateEvent.selecting_limit)
    await message.answer("Лимит участников от класса:", reply_markup=get_event_limit_keyboard())


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
    await callback.message.edit_text("Описание (необязательно):", reply_markup=get_event_description_keyboard())


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
    await _show_event_preview(message, state)


@router.callback_query(AdminCreateEvent.entering_description, F.data == "event_skip_desc")
async def event_skip_description(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(event_description=None)
    await _show_event_preview(callback.message, state, edit=True)


async def _show_event_preview(message, state: FSMContext, edit=False):
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


# ── Просмотр и управление мероприятиями ──────────────────────────────────────

@router.callback_query(F.data == "menu:events_admin")
async def menu_events_admin(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    events = event_repo.get_all_events()
    if not events:
        await callback.message.edit_text("Мероприятий пока нет.", reply_markup=get_admin_main_menu())
        return
    await callback.message.edit_text("Мероприятия:", reply_markup=_events_page_markup(events, 0))


@router.callback_query(F.data.startswith("admin_events_page:"))
async def admin_events_paginate(callback: CallbackQuery):
    await callback.answer()
    page = int(callback.data.split(":")[1])
    events = event_repo.get_all_events()
    if not events:
        await callback.message.edit_text("Мероприятий нет.", reply_markup=get_admin_main_menu())
        return
    await callback.message.edit_text("Мероприятия:", reply_markup=_events_page_markup(events, page))


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
    await callback.message.edit_text("Мероприятия:", reply_markup=_events_page_markup(events, 0))


@router.callback_query(F.data.startswith("event_export:"))
async def export_event_participants(callback: CallbackQuery):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    event = event_repo.get_event(event_id)
    if not event:
        await callback.message.edit_text("Мероприятие не найдено.")
        return
    participants = event_repo.get_all_registrations(event_id)
    total = len(participants)

    lines = [f"Мероприятие: {event['title']}", f"Дата: {event['date']}", f"Всего участников: {total}", ""]
    by_class = {}
    for p in participants:
        by_class.setdefault(p["class"], []).append(p["student_name"])
    for cls, names in sorted(by_class.items()):
        lines.append(f"=== {cls} ({len(names)} чел.) ===")
        for name in names:
            lines.append(f"  {name}")
        lines.append("")

    text_content = "\n".join(lines)
    file = BufferedInputFile(
        text_content.encode("utf-8"),
        filename=f"участники_{event['title']}_{event['date']}.txt",
    )
    await callback.message.answer_document(file, caption=f"Список участников: {event['title']}")
