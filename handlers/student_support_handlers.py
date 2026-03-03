"""
Handlers для анонимного чата с психологом — сторона ученика.
"""
from aiogram import Router, F, Bot, Dispatcher
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from database.support_repository import SupportRepository
from database.user_repository import UserRepository
from handlers.states import StudentSupport
from keyboards.student_keyboards import (
    get_student_main_menu,
    get_student_chat_reply_keyboard,
    get_support_confirm_keyboard,
    get_support_open_keyboard,
    get_support_history_keyboard,
    get_support_back_keyboard,
)
from utils.config_loader import get_psychologist_user_id
from keyboards.psychologist_keyboards import get_psychologist_notify_keyboard

router = Router()

support_repo = SupportRepository()
user_repo = UserRepository()


# ── Вспомогательные ───────────────────────────────────────────────────────────

def _format_history(messages: list, chat: dict) -> str:
    """Форматирует историю сообщений для отображения."""
    if not messages:
        return "Сообщений пока нет. Напиши что-нибудь — психолог ответит!"
    lines = []
    for m in messages:
        time = m["created_at"][11:16]  # HH:MM
        if m["sender_type"] == "student":
            lines.append(f"<b>Ты</b> [{time}]:\n{m['text']}")
        else:
            lines.append(f"<b>Психолог</b> [{time}]:\n{m['text']}")
    return "\n\n".join(lines)


def _chat_header(chat: dict) -> str:
    status = "активен" if chat["status"] == "active" else "завершён"
    anon = "анонимный" if chat["is_anonymous"] else "личность раскрыта"
    return f"💬 <b>Чат #{chat['id']}</b> ({status}, {anon})\n\n"


async def _notify_psychologist(bot: Bot, dp: Dispatcher, chat_id: int, text: str) -> None:
    """Переслать сообщение психологу. Если психолог уже в этом чате — без кнопки."""
    psych_id = get_psychologist_user_id()
    if not psych_id:
        return
    # Проверяем, находится ли психолог в FSM in_chat для этого чата
    key = StorageKey(bot_id=bot.id, chat_id=psych_id, user_id=psych_id)
    state_data = await dp.storage.get_data(key)
    psych_in_this_chat = state_data.get("psych_chat_id") == chat_id

    try:
        if psych_in_this_chat:
            await bot.send_message(psych_id, text, parse_mode="HTML")
        else:
            await bot.send_message(
                psych_id,
                text,
                parse_mode="HTML",
                reply_markup=get_psychologist_notify_keyboard(chat_id),
            )
    except Exception:
        pass


# ── Точка входа ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:support")
async def menu_support(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    active = support_repo.get_active_chat(callback.from_user.id)
    if active:
        msgs = support_repo.get_messages(active["id"], limit=5)
        history_preview = _format_history(msgs, active)
        text = (
            _chat_header(active)
            + history_preview
            + "\n\n<i>Напиши сообщение или воспользуйся кнопками.</i>"
        )
    else:
        text = (
            "💬 <b>Анонимная поддержка</b>\n\n"
            "Ты можешь пообщаться с психологом анонимно. "
            "Никто не узнает, кто ты, пока ты сам не захочешь раскрыть личность.\n\n"
            "Нажми <b>«Открыть анонимный чат»</b>, чтобы начать."
        )
    await callback.message.edit_text(
        text, parse_mode="HTML",
        reply_markup=get_support_open_keyboard(has_active_chat=bool(active)),
    )


# ── Создать новый чат ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "support:create")
async def support_create(callback: CallbackQuery, state: FSMContext, bot: Bot, dp: Dispatcher):
    await callback.answer()
    chat_id = support_repo.create_chat(callback.from_user.id)
    await state.set_state(StudentSupport.in_chat)
    await state.update_data(support_chat_id=chat_id)

    psych_id = get_psychologist_user_id()
    if psych_id:
        try:
            await bot.send_message(
                psych_id,
                f"🆕 Открыт новый анонимный чат <b>#{chat_id}</b>.",
                parse_mode="HTML",
                reply_markup=get_psychologist_notify_keyboard(chat_id),
            )
        except Exception:
            pass

    await callback.message.edit_text(
        f"💬 <b>Чат #{chat_id} открыт</b>\n\n"
        "Ты анонимен. Пиши свои мысли — психолог ответит.",
        parse_mode="HTML",
    )
    await callback.message.answer(
        "Используй кнопки ниже для управления чатом.",
        reply_markup=get_student_chat_reply_keyboard(is_anonymous=True),
    )


# ── Открыть существующий чат ──────────────────────────────────────────────────

@router.callback_query(F.data == "support:open")
async def support_open(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    chat = support_repo.get_active_chat(callback.from_user.id)
    if not chat:
        await callback.message.edit_text(
            "Активного чата нет.", reply_markup=get_support_open_keyboard(False)
        )
        return
    await state.set_state(StudentSupport.in_chat)
    await state.update_data(support_chat_id=chat["id"])

    msgs = support_repo.get_messages(chat["id"])
    history = _format_history(msgs, chat)
    await callback.message.edit_text(
        _chat_header(chat) + history,
        parse_mode="HTML",
    )
    await callback.message.answer(
        "Продолжай общение — пиши сообщение:",
        reply_markup=get_student_chat_reply_keyboard(is_anonymous=bool(chat["is_anonymous"])),
    )


# ── Получение сообщения от ученика ────────────────────────────────────────────

@router.message(StudentSupport.in_chat, F.text == "🚪 Завершить чат")
async def support_close_via_keyboard(message: Message, state: FSMContext):
    """Нажатие кнопки «Завершить чат» в ReplyKeyboard."""
    await state.set_state(StudentSupport.confirm_close)
    await message.answer(
        "🚪 <b>Завершить чат?</b>\n\n"
        "Переписка сохранится в истории, но продолжить её будет нельзя.",
        parse_mode="HTML",
        reply_markup=get_support_confirm_keyboard("close"),
    )


@router.message(StudentSupport.in_chat, F.text == "◀️ В главное меню")
async def support_menu_via_keyboard(message: Message, state: FSMContext):
    """Нажатие кнопки «В главное меню» в ReplyKeyboard."""
    await state.clear()
    await message.answer(
        "Главное меню:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await message.answer("Выбери действие:", reply_markup=get_student_main_menu())


@router.message(StudentSupport.in_chat, F.text == "👤 Открыть личность")
async def support_reveal_via_keyboard(message: Message, state: FSMContext):
    """Нажатие кнопки «Открыть личность» в ReplyKeyboard."""
    await state.set_state(StudentSupport.confirm_reveal)
    await message.answer(
        "👤 <b>Раскрыть личность?</b>\n\n"
        "Психолог увидит твоё имя и класс. "
        "Это действие <b>нельзя отменить</b>.",
        parse_mode="HTML",
        reply_markup=get_support_confirm_keyboard("reveal"),
    )


@router.message(StudentSupport.in_chat, F.text)
async def support_student_message(message: Message, state: FSMContext, bot: Bot, dp: Dispatcher):
    data = await state.get_data()
    chat_id = data.get("support_chat_id")
    if not chat_id:
        await state.clear()
        return

    chat = support_repo.get_chat(chat_id)
    if not chat or chat["status"] != "active":
        await state.clear()
        await message.answer("Чат уже завершён.", reply_markup=ReplyKeyboardRemove())
        await message.answer("Выбери действие:", reply_markup=get_student_main_menu())
        return

    support_repo.add_message(chat_id, "student", message.text)

    # Формируем префикс для психолога
    if chat["is_anonymous"]:
        prefix = f"Аноним #{chat_id}"
    else:
        u = user_repo.get_user(message.from_user.id)
        prefix = f"{u['ФИ']}, {u['class']}" if u else f"Чат #{chat_id}"

    await _notify_psychologist(bot, dp, chat_id, f"[{prefix}]:\n{message.text}")
    # НЕ отвечаем студенту — сообщение просто отправлено


@router.message(StudentSupport.in_chat)
async def support_student_non_text(message: Message, state: FSMContext):
    await message.answer("Пожалуйста, отправь текстовое сообщение.")


# ── Раскрыть личность ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "support:reveal")
async def support_reveal_ask(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(StudentSupport.confirm_reveal)
    await callback.message.edit_text(
        "👤 <b>Раскрыть личность?</b>\n\n"
        "Психолог увидит твоё имя и класс. "
        "Это действие <b>нельзя отменить</b>.",
        parse_mode="HTML",
        reply_markup=get_support_confirm_keyboard("reveal"),
    )


@router.callback_query(StudentSupport.confirm_reveal, F.data == "support:confirm_reveal")
async def support_reveal_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    chat_id = data.get("support_chat_id")

    support_repo.reveal_identity(chat_id)
    await state.set_state(StudentSupport.in_chat)

    user = user_repo.get_user(callback.from_user.id)
    identity = f"{user['ФИ']}, {user['class']}" if user else "—"

    psych_id = get_psychologist_user_id()
    if psych_id:
        try:
            await bot.send_message(
                psych_id,
                f"👤 Ученик в чате <b>#{chat_id}</b> раскрыл личность:\n<b>{identity}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await callback.message.edit_text(
        f"✅ Личность раскрыта. Психолог теперь видит: <b>{identity}</b>",
        parse_mode="HTML",
    )
    await callback.message.answer(
        "Продолжай общение:",
        reply_markup=get_student_chat_reply_keyboard(is_anonymous=False),
    )


# ── Завершить чат ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "support:close")
async def support_close_ask(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(StudentSupport.confirm_close)
    await callback.message.edit_text(
        "🚪 <b>Завершить чат?</b>\n\n"
        "Переписка сохранится в истории, но продолжить её будет нельзя.",
        parse_mode="HTML",
        reply_markup=get_support_confirm_keyboard("close"),
    )


@router.callback_query(StudentSupport.confirm_close, F.data == "support:confirm_close")
async def support_close_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    chat_id = data.get("support_chat_id")

    support_repo.close_chat(chat_id)
    await state.clear()

    psych_id = get_psychologist_user_id()
    if psych_id:
        try:
            await bot.send_message(
                psych_id,
                f"🚪 Ученик завершил чат <b>#{chat_id}</b>.",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await callback.message.edit_text(
        "Чат завершён. Если захочешь — можешь открыть новый.",
    )
    await callback.message.answer(
        "Выбери действие:",
        reply_markup=ReplyKeyboardRemove(),
    )
    await callback.message.answer(
        "Анонимная поддержка:",
        reply_markup=get_support_open_keyboard(has_active_chat=False),
    )


# ── Отмена подтверждения ──────────────────────────────────────────────────────

@router.callback_query(F.data == "support:cancel_action")
async def support_cancel_action(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    chat_id = data.get("support_chat_id")
    chat = support_repo.get_chat(chat_id) if chat_id else None
    await state.set_state(StudentSupport.in_chat)
    await callback.message.edit_text("Действие отменено. Продолжай общаться:")
    await callback.message.answer(
        "Пиши сообщение:",
        reply_markup=get_student_chat_reply_keyboard(
            is_anonymous=bool(chat["is_anonymous"]) if chat else True
        ),
    )


# ── Выход в главное меню (без закрытия чата) ──────────────────────────────────

@router.callback_query(F.data == "support:menu")
async def support_to_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "Главное меню:", reply_markup=get_student_main_menu()
    )


# ── История чатов ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "support:history")
async def support_history(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    chats = support_repo.get_student_chats(callback.from_user.id)
    closed = [c for c in chats if c["status"] == "closed"]
    if not closed:
        await callback.message.edit_text(
            "История чатов пуста.",
            reply_markup=get_support_open_keyboard(
                has_active_chat=bool(support_repo.get_active_chat(callback.from_user.id))
            ),
        )
        return
    await callback.message.edit_text(
        "📋 <b>История чатов:</b>",
        parse_mode="HTML",
        reply_markup=get_support_history_keyboard(closed),
    )


@router.callback_query(F.data.startswith("support:view_history:"))
async def support_view_history_chat(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    chat_id = int(callback.data.split(":")[2])
    chat = support_repo.get_chat(chat_id)
    if not chat or chat["student_user_id"] != callback.from_user.id:
        await callback.message.edit_text("Чат не найден.")
        return
    msgs = support_repo.get_messages(chat_id)
    history = _format_history(msgs, chat)
    await callback.message.edit_text(
        _chat_header(chat) + history,
        parse_mode="HTML",
        reply_markup=get_support_back_keyboard(),
    )
