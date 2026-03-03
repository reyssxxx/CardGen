"""
Общие handlers для всех пользователей (регистрация, /start, /cancel)
"""
import os
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from dotenv import load_dotenv

from database.user_repository import UserRepository
from handlers.states import RegistrationStates
from keyboards.common_keyboards import (
    get_registration_keyboard,
    get_class_selection_keyboard,
    get_name_selection_keyboard,
    get_confirm_registration_keyboard,
    get_cancel_keyboard,
)
from keyboards.student_keyboards import get_student_main_menu
from keyboards.admin_keyboards import get_admin_main_menu
from keyboards.teacher_keyboards import get_teacher_main_menu
from utils.config_loader import (
    get_all_classes, get_students_by_class,
    is_teacher, get_teacher_name,
    is_psychologist, get_psychologist_name,
)
from keyboards.psychologist_keyboards import get_psychologist_main_menu

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

router = Router()


def _is_env_admin(user_id: int) -> bool:
    load_dotenv(override=True)
    return user_id in {int(x) for x in os.getenv("ADMIN_ID", "").split(",") if x.strip()}


async def _show_menu(target, user, is_new_message=False):
    """Показать главное меню пользователю."""
    name_first = user["ФИ"].split()[0]
    if user["isAdmin"]:
        text = f"Добро пожаловать, {name_first}! Выбери действие:"
        kb = get_admin_main_menu()
    elif user["isTeacher"]:
        text = f"Добро пожаловать, {name_first}! Выбери действие:"
        kb = get_teacher_main_menu()
    else:
        cls = user["class"]
        text = f"Привет, {name_first}! (Класс: {cls})\nЧто хочешь сделать?"
        kb = get_student_main_menu()
    if is_new_message:
        await target.answer(text, reply_markup=kb)
    else:
        await target.edit_text(text, reply_markup=kb)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    rm = await message.answer(".", reply_markup=ReplyKeyboardRemove())
    await rm.delete()

    user_id = message.from_user.id
    user_repo = UserRepository()

    # Автоматическая регистрация/вход для админов из .env
    if _is_env_admin(user_id):
        user = user_repo.get_user(user_id)
        if not user:
            name = message.from_user.full_name or "Администратор"
            user_repo.register_admin(name, user_id)
            user = user_repo.get_user(user_id)
        await _show_menu(message, user, is_new_message=True)
        return

    # Автоматическая регистрация/вход для учителей из teachers.json
    if is_teacher(user_id):
        user = user_repo.get_user(user_id)
        if not user:
            name = get_teacher_name(user_id) or message.from_user.full_name or "Учитель"
            user_repo.register_teacher(name, user_id)
            user = user_repo.get_user(user_id)
        await _show_menu(message, user, is_new_message=True)
        return

    # Вход для психолога (не сохраняем в БД — отдельная роль)
    if is_psychologist(user_id):
        name = get_psychologist_name(user_id) or message.from_user.full_name or "Психолог"
        await message.answer(
            f"Добро пожаловать, {name.split()[0]}! Выбери действие:",
            reply_markup=get_psychologist_main_menu(),
        )
        return

    # Обычный пользователь — проверяем регистрацию
    user = user_repo.get_user(user_id)
    if user:
        await _show_menu(message, user, is_new_message=True)
        return

    # Не зарегистрирован — предлагаем роль ученика или учителя
    await message.answer(
        "Привет! Добро пожаловать в бот Лицея ЮФУ.\n\nВыбери свою роль:",
        reply_markup=get_registration_keyboard(),
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    user_repo = UserRepository()
    user = user_repo.get_user(message.from_user.id)
    if user:
        await _show_menu(message, user, is_new_message=True)
    else:
        await message.answer("Действие отменено.")


@router.callback_query(F.data == "menu:back_student")
async def back_to_student_menu(callback: CallbackQuery):
    await callback.answer()
    user_repo = UserRepository()
    user = user_repo.get_user(callback.from_user.id)
    if user:
        await _show_menu(callback.message, user)


@router.callback_query(F.data == "menu:back_teacher")
async def back_to_teacher_menu(callback: CallbackQuery):
    await callback.answer()
    user_repo = UserRepository()
    user = user_repo.get_user(callback.from_user.id)
    if user:
        await _show_menu(callback.message, user)


@router.callback_query(F.data == "register_student")
async def start_student_registration(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    classes = get_all_classes()
    if not classes:
        await callback.message.edit_text(
            "Список классов пуст. Обратись к администратору.",
            reply_markup=get_cancel_keyboard("reg_cancel"),
        )
        return
    await state.set_state(RegistrationStates.selecting_class)
    await callback.message.edit_text(
        "Регистрация ученика\n\nВыбери свой класс:",
        reply_markup=get_class_selection_keyboard(classes),
    )


@router.callback_query(RegistrationStates.selecting_class, F.data.startswith("reg_class:"))
async def select_class(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    class_name = callback.data.split(":", 1)[1]
    names = get_students_by_class(class_name)
    if not names:
        await callback.message.edit_text(
            f"Класс {class_name} пуст. Обратись к администратору.",
            reply_markup=get_cancel_keyboard("reg_cancel"),
        )
        return
    await state.update_data(selected_class=class_name)
    await state.set_state(RegistrationStates.selecting_name)
    await callback.message.edit_text(
        f"Класс {class_name}\n\nВыбери своё имя из списка:",
        reply_markup=get_name_selection_keyboard(names),
    )


@router.callback_query(RegistrationStates.selecting_name, F.data.startswith("reg_name:"))
async def select_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    name = callback.data.split(":", 1)[1]
    data = await state.get_data()
    class_name = data["selected_class"]
    await state.update_data(selected_name=name)
    await state.set_state(RegistrationStates.confirming)
    await callback.message.edit_text(
        f"Подтверди:\n\n<b>{name}</b>\nКласс: <b>{class_name}</b>\n\nЭто ты?",
        reply_markup=get_confirm_registration_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(RegistrationStates.confirming, F.data == "reg_confirm")
async def confirm_registration(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    name = data["selected_name"]
    class_name = data["selected_class"]
    user_repo = UserRepository()
    success = user_repo.register_student(name, callback.from_user.id, class_name)
    if success:
        await state.clear()
        await callback.message.edit_text(
            f"Ты зарегистрирован как <b>{name}</b>, класс <b>{class_name}</b>.\n\nЧто хочешь сделать?",
            parse_mode="HTML",
            reply_markup=get_student_main_menu(),
        )
    else:
        # Не чистим FSM — пользователь может вернуться к выбору имени через reg_back_name
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.types import InlineKeyboardButton
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="◀️ Выбрать другое имя", callback_data="reg_back_name"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="reg_cancel"),
        )
        await callback.message.edit_text(
            "⚠️ Это имя уже занято другим пользователем.\n"
            "Выбери другое имя или обратись к администратору.",
            reply_markup=kb.as_markup(),
        )


@router.callback_query(RegistrationStates.confirming, F.data == "reg_back_name")
async def back_to_name(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    class_name = data["selected_class"]
    names = get_students_by_class(class_name)
    await state.set_state(RegistrationStates.selecting_name)
    await callback.message.edit_text(
        f"Класс {class_name}\n\nВыбери своё имя:",
        reply_markup=get_name_selection_keyboard(names),
    )


@router.callback_query(RegistrationStates.selecting_name, F.data == "reg_back_class")
async def back_to_class(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    classes = get_all_classes()
    await state.set_state(RegistrationStates.selecting_class)
    await callback.message.edit_text(
        "Регистрация ученика\n\nВыбери свой класс:",
        reply_markup=get_class_selection_keyboard(classes),
    )


@router.callback_query(F.data == "register_teacher_request")
async def teacher_not_in_list(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text(
        "👩‍🏫 Доступ учителей настраивается администратором.\n\n"
        "Попроси администратора добавить твой Telegram ID в список учителей.\n"
        "Твой ID: <code>{}</code>".format(callback.from_user.id),
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard("reg_cancel"),
    )


@router.callback_query(F.data == "reg_cancel")
async def cancel_registration(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(
        "Привет! Добро пожаловать в бот Лицея ЮФУ.\n\nВыбери свою роль:",
        reply_markup=get_registration_keyboard(),
    )
