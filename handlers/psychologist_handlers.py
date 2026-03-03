"""
Handlers для психолога: просмотр чатов поддержки и переписка с учениками.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.support_repository import SupportRepository
from database.user_repository import UserRepository
from handlers.states import PsychologistChat
from keyboards.psychologist_keyboards import (
    get_psychologist_main_menu,
    get_psychologist_chats_keyboard,
    get_psychologist_in_chat_keyboard,
)
from keyboards.student_keyboards import get_support_back_keyboard
from utils.config_loader import is_psychologist

router = Router()

support_repo = SupportRepository()
user_repo = UserRepository()


# ── Вспомогательные ───────────────────────────────────────────────────────────

def _is_psychologist(user_id: int) -> bool:
    return is_psychologist(user_id)


def _format_history(messages: list) -> str:
    if not messages:
        return "<i>Сообщений пока нет.</i>"
    lines = []
    for m in messages:
        time = m["created_at"][11:16]
        if m["sender_type"] == "student":
            lines.append(f"<b>Ученик</b> [{time}]:\n{m['text']}")
        else:
            lines.append(f"<b>Вы</b> [{time}]:\n{m['text']}")
    return "\n\n".join(lines)


def _chat_title(chat: dict) -> str:
    if chat.get("is_anonymous"):
        return f"Аноним #{chat['id']}"
    # Если личность раскрыта — ищем пользователя
    user = user_repo.get_user(chat["student_user_id"])
    if user:
        return f"{user['ФИ']}, {user['class']} (чат #{chat['id']})"
    return f"Чат #{chat['id']}"


# ── Главное меню психолога ────────────────────────────────────────────────────

@router.callback_query(F.data == "psych:menu")
async def psych_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not _is_psychologist(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text(
        "👋 Меню психолога:", reply_markup=get_psychologist_main_menu()
    )


# ── Список активных чатов ─────────────────────────────────────────────────────

@router.callback_query(F.data == "psych:active")
async def psych_active_chats(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not _is_psychologist(callback.from_user.id):
        return
    await state.clear()
    chats = support_repo.get_all_active_chats()
    if not chats:
        await callback.message.edit_text(
            "Нет активных чатов.", reply_markup=get_psychologist_main_menu()
        )
        return
    await callback.message.edit_text(
        "💬 <b>Активные чаты:</b>",
        parse_mode="HTML",
        reply_markup=get_psychologist_chats_keyboard(chats, back_callback="psych:menu"),
    )


# ── Список завершённых чатов ──────────────────────────────────────────────────

@router.callback_query(F.data == "psych:closed")
async def psych_closed_chats(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not _is_psychologist(callback.from_user.id):
        return
    await state.clear()
    chats = support_repo.get_all_closed_chats()
    if not chats:
        await callback.message.edit_text(
            "Завершённых чатов нет.", reply_markup=get_psychologist_main_menu()
        )
        return
    await callback.message.edit_text(
        "📋 <b>Завершённые чаты:</b>",
        parse_mode="HTML",
        reply_markup=get_psychologist_chats_keyboard(chats, back_callback="psych:menu"),
    )


# ── Открыть чат ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("psych:chat:"))
async def psych_open_chat(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not _is_psychologist(callback.from_user.id):
        return
    chat_id = int(callback.data.split(":")[2])
    chat = support_repo.get_chat(chat_id)
    if not chat:
        await callback.message.edit_text("Чат не найден.")
        return

    await state.set_state(PsychologistChat.in_chat)
    await state.update_data(psych_chat_id=chat_id)

    title = _chat_title(chat)
    msgs = support_repo.get_messages(chat_id)
    history = _format_history(msgs)
    is_closed = chat["status"] == "closed"

    status_text = "\n\n<i>⚠️ Чат завершён. Ответить нельзя.</i>" if is_closed else \
                  "\n\n<i>Напишите ответ — он будет отправлен ученику.</i>"

    await callback.message.edit_text(
        f"💬 <b>{title}</b>\n\n{history}{status_text}",
        parse_mode="HTML",
        reply_markup=get_psychologist_in_chat_keyboard(chat_id, is_closed),
    )


# ── Ответ психолога ───────────────────────────────────────────────────────────

@router.message(PsychologistChat.in_chat)
async def psych_reply(message: Message, state: FSMContext, bot: Bot):
    if not _is_psychologist(message.from_user.id):
        return
    if not message.text:
        await message.answer("Пожалуйста, отправь текстовое сообщение.")
        return

    data = await state.get_data()
    chat_id = data.get("psych_chat_id")
    if not chat_id:
        await state.clear()
        return

    chat = support_repo.get_chat(chat_id)
    if not chat:
        await message.answer("Чат не найден.")
        return
    if chat["status"] != "active":
        await message.answer("Чат уже завершён — ответить нельзя.")
        return

    support_repo.add_message(chat_id, "psychologist", message.text)

    # Уведомить ученика
    try:
        await bot.send_message(
            chat["student_user_id"],
            f"💬 <b>Психолог ответил:</b>\n\n{message.text}",
            parse_mode="HTML",
            reply_markup=get_support_back_keyboard(),
        )
    except Exception:
        pass

    await message.answer(
        "✅ Ответ отправлен ученику.",
        reply_markup=get_psychologist_in_chat_keyboard(chat_id, is_closed=False),
    )


# ── Завершить чат (психолог) ──────────────────────────────────────────────────

@router.callback_query(F.data.startswith("psych:close:"))
async def psych_close_chat(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    if not _is_psychologist(callback.from_user.id):
        return
    chat_id = int(callback.data.split(":")[2])
    chat = support_repo.get_chat(chat_id)
    if not chat:
        return

    support_repo.close_chat(chat_id)
    await state.clear()

    # Уведомить ученика
    try:
        await bot.send_message(
            chat["student_user_id"],
            "🚪 Психолог завершил чат. Если хочешь — можешь открыть новый.",
            reply_markup=get_support_back_keyboard(),
        )
    except Exception:
        pass

    await callback.message.edit_text(
        f"✅ Чат #{chat_id} завершён.",
        reply_markup=get_psychologist_main_menu(),
    )


# ── Выйти из чата в список (без закрытия) ────────────────────────────────────

@router.callback_query(F.data == "psych:exit_chat")
async def psych_exit_chat(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not _is_psychologist(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text(
        "👋 Меню психолога:", reply_markup=get_psychologist_main_menu()
    )
