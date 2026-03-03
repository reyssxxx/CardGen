"""
Хендлеры администратора: создание и управление мероприятиями.
"""
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from handlers.admin.common import is_admin, user_repo, event_repo
from handlers.states import AdminCreateEvent, AdminAddSection
from keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_event_description_keyboard,
    get_admin_events_keyboard,
    get_event_manage_keyboard,
    get_event_manage_day_keyboard,
    get_section_skip_keyboard,
    get_section_capacity_keyboard,
    get_admin_section_detail_keyboard,
    get_event_delete_confirm_keyboard,
    get_cancel_keyboard,
)

router = Router()


# ── Создание дня мероприятий ──────────────────────────────────────────────────

@router.callback_query(F.data == "menu:create_event")
async def menu_create_event(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    await state.update_data(admin_id=callback.from_user.id)
    await state.set_state(AdminCreateEvent.entering_title)
    await callback.message.edit_text(
        "Создание дня мероприятий\n\nВведи название (например: «День словесности»):",
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
        await message.answer("Неверный формат. Введи дату в формате ДД.ММ.ГГГГ (например: 15.03.2026)")
        return
    await state.update_data(event_date=date_str)
    await state.set_state(AdminCreateEvent.entering_description)
    await message.answer("Описание дня (необязательно):", reply_markup=get_event_description_keyboard())


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


# ── Добавление секций ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("section_add:"))
async def section_add_start(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    await state.update_data(section_event_id=event_id)
    await state.set_state(AdminAddSection.entering_title)
    await callback.message.edit_text("Название секции:", reply_markup=get_cancel_keyboard())


@router.message(AdminAddSection.entering_title)
async def section_enter_title(message: Message, state: FSMContext):
    await state.update_data(section_title=message.text.strip())
    await state.set_state(AdminAddSection.entering_host)
    await message.answer("Ведущий секции:", reply_markup=get_section_skip_keyboard("sec_skip_host"))


@router.callback_query(AdminAddSection.entering_host, F.data == "sec_skip_host")
async def section_skip_host(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(section_host=None)
    await state.set_state(AdminAddSection.entering_time)
    await callback.message.edit_text("Время секции (ЧЧ:ММ):", reply_markup=get_section_skip_keyboard("sec_skip_time"))


@router.message(AdminAddSection.entering_host)
async def section_enter_host(message: Message, state: FSMContext):
    await state.update_data(section_host=message.text.strip())
    await state.set_state(AdminAddSection.entering_time)
    await message.answer("Время секции (ЧЧ:ММ):", reply_markup=get_section_skip_keyboard("sec_skip_time"))


@router.callback_query(AdminAddSection.entering_time, F.data == "sec_skip_time")
async def section_skip_time(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(section_time=None)
    await state.set_state(AdminAddSection.selecting_capacity)
    await callback.message.edit_text("Лимит участников секции:", reply_markup=get_section_capacity_keyboard())


@router.message(AdminAddSection.entering_time)
async def section_enter_time(message: Message, state: FSMContext):
    from utils.validators import validate_time
    time_str = message.text.strip()
    if not validate_time(time_str):
        await message.answer("Неверный формат. Введи время в формате ЧЧ:ММ (например: 14:30)")
        return
    await state.update_data(section_time=time_str)
    await state.set_state(AdminAddSection.selecting_capacity)
    await message.answer("Лимит участников секции:", reply_markup=get_section_capacity_keyboard())


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
    await callback.message.edit_text("Описание секции (необязательно):", reply_markup=get_section_skip_keyboard("sec_skip_desc"))


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
    await message.answer("Описание секции (необязательно):", reply_markup=get_section_skip_keyboard("sec_skip_desc"))


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
    await state.set_state(AdminCreateEvent.managing)
    await state.update_data(event_id=event_id)
    await _show_event_manage(message, event_id, edit=edit)


# ── Просмотр и удаление секции ────────────────────────────────────────────────

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


# ── Публикация ────────────────────────────────────────────────────────────────

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


# ── Управление из списка мероприятий ─────────────────────────────────────────

@router.callback_query(F.data.startswith("event_manage:"))
async def event_manage_from_list(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    event_id = int(callback.data.split(":")[1])
    await state.update_data(event_id=event_id)
    await state.set_state(AdminCreateEvent.managing)
    await _show_event_manage(callback.message, event_id, edit=True)


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
    await callback.message.edit_text("Мероприятия:", reply_markup=get_admin_events_keyboard(events))


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
    total = event_repo.get_total_registrations(event_id)
    text = f"<b>{event['title']}</b> — {event['date']}\nЗаписалось: <b>{total}</b>"
    pub = event.get("published", 1)
    if not pub:
        text += "\n📝 Черновик (не опубликовано)"
    if sections:
        text += "\n\n<b>Секции:</b>"
        for s in sections:
            count = event_repo.get_section_count(s["id"])
            time_str = f"{s['time']} " if s.get('time') else ""
            cap_str = f" ({count}" + (f"/{s['capacity']}" if s.get('capacity') else "") + ")"
            text += f"\n• {time_str}{s['title']}{cap_str}"
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


# ── Экспорт участников ────────────────────────────────────────────────────────

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
        regs = event_repo.get_all_registrations(event_id)
        lines.append(f"=== Участники ({len(regs)} чел.) ===")
        for p in regs:
            lines.append(f"  {p['student_name']} ({p['class']})")
    text_content = "\n".join(lines)
    file = BufferedInputFile(
        text_content.encode("utf-8"),
        filename=f"участники_{event['title']}_{event['date']}.txt",
    )
    await callback.message.answer_document(file, caption=f"Список участников: {event['title']}")
