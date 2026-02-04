"""
Обработчики команд администратора
"""
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from os import getenv

from database.photo_repository import PhotoRepository
from database.user_repository import UserRepository
from services.mailing_service import MailingService
from utils.formatters import format_journal_status
from utils.config_loader import get_config
from keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_admin_send_audience_keyboard,
    get_admin_send_confirmation_keyboard,
    get_cancel_keyboard
)
from handlers.states import AdminManagement

router = Router()

# Получить список админов из .env
ADMIN_IDS_STR = getenv('ADMINS', '')
ADMINS = [id.strip() for id in ADMIN_IDS_STR.split(',') if id.strip()]


def is_admin(user_id: int) -> bool:
    """
    Проверка, является ли пользователь админом

    Args:
        user_id: Telegram ID пользователя

    Returns:
        True если пользователь админ
    """
    return str(user_id) in ADMINS


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    """
    Команда /admin - главное меню администратора
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    await message.answer(
        "👨‍💼 Панель администратора\n\n"
        "Выберите действие:",
        reply_markup=get_admin_main_menu()
    )


@router.message(Command("journal_status"))
@router.message(F.text == "📊 Состояние журнала")
async def cmd_journal_status(message: Message):
    """
    Команда /journal_status - состояние журнала (кто загружал фото)
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    try:
        photo_repo = PhotoRepository()

        # Получить загрузки за последнюю неделю
        uploads = photo_repo.get_all_recent_uploads(days=7)

        # Форматировать отчет
        status_message = format_journal_status(uploads)

        await message.answer(status_message)

    except Exception as e:
        print(f"[ERROR] Failed to get journal status: {e}")
        await message.answer(f"❌ Ошибка при получении статуса журнала: {e}")


@router.message(Command("force_mailing"))
@router.message(F.text == "🔄 Принудительная рассылка")
async def cmd_force_mailing(message: Message):
    """
    Команда /force_mailing - принудительная рассылка табелей
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    try:
        await message.answer("⏳ Запускаю рассылку табелей...")

        # Получить scheduler из bot data (будет установлен в main.py)
        scheduler = message.bot.get("scheduler")

        if not scheduler:
            # Fallback: создать MailingService и запустить напрямую
            print("[WARNING] Scheduler not found in bot data, using fallback")
            mailing_service = MailingService(message.bot)
            await mailing_service.send_grade_cards_to_all()
        else:
            await scheduler.trigger_manual_mailing()

        await message.answer("✅ Рассылка завершена! Проверьте логи для деталей.")

    except Exception as e:
        print(f"[ERROR] Force mailing failed: {e}")
        import traceback
        traceback.print_exc()
        await message.answer(f"❌ Ошибка при рассылке: {e}")


@router.message(Command("admin_send"))
@router.message(F.text == "📢 Массовая рассылка")
async def cmd_admin_send(message: Message, state: FSMContext):
    """
    Команда /admin_send - начало процесса массовой рассылки
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    try:
        # Получить список классов из конфига
        config = get_config()
        teachers = config.get('teachers', [])

        # Извлечь уникальные классы
        classes = list(set(teacher[2] for teacher in teachers if len(teacher) > 2))
        classes.sort()

        await message.answer(
            "📢 Массовая рассылка\n\n"
            "Выберите аудиторию для рассылки:",
            reply_markup=get_admin_send_audience_keyboard(classes)
        )

        await state.set_state(AdminManagement.admin_send_selecting_audience)

    except Exception as e:
        print(f"[ERROR] Failed to start admin_send: {e}")
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(AdminManagement.admin_send_selecting_audience)
async def process_audience_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора аудитории для рассылки
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора")
        return

    if callback.data == "admin_cancel":
        await callback.message.edit_text("❌ Рассылка отменена")
        await state.clear()
        return

    # Сохранить выбранную аудиторию
    if callback.data == "admin_send:all_students":
        audience_type = "all_students"
        audience_name = "Всем ученикам"
    elif callback.data == "admin_send:all_teachers":
        audience_type = "all_teachers"
        audience_name = "Всем учителям"
    elif callback.data.startswith("admin_send_class:"):
        class_name = callback.data.split(":", 1)[1]
        audience_type = "class"
        audience_name = f"Классу {class_name}"
        await state.update_data(class_name=class_name)
    else:
        await callback.answer("❌ Неизвестная аудитория")
        return

    await state.update_data(
        audience_type=audience_type,
        audience_name=audience_name
    )

    await callback.message.edit_text(
        f"📢 Рассылка: {audience_name}\n\n"
        "Введите текст сообщения для рассылки:",
        reply_markup=get_cancel_keyboard()
    )

    await state.set_state(AdminManagement.admin_send_message)
    await callback.answer()


@router.callback_query(AdminManagement.admin_send_message, F.data == "admin_cancel")
async def cancel_admin_send_message(callback: CallbackQuery, state: FSMContext):
    """
    Отмена ввода сообщения
    """
    await callback.message.edit_text("❌ Рассылка отменена")
    await state.clear()
    await callback.answer()


@router.message(AdminManagement.admin_send_message)
async def process_admin_send_message(message: Message, state: FSMContext):
    """
    Получение текста сообщения для рассылки
    """
    if not is_admin(message.from_user.id):
        await message.answer("❌ У вас нет прав администратора")
        return

    message_text = message.text

    if len(message_text) > 4000:
        await message.answer("❌ Сообщение слишком длинное (максимум 4000 символов)")
        return

    # Сохранить сообщение
    await state.update_data(message_text=message_text)

    # Получить данные для подтверждения
    data = await state.get_data()
    audience_name = data.get('audience_name', 'Unknown')

    confirmation_text = (
        f"📢 Подтверждение рассылки\n\n"
        f"Аудитория: {audience_name}\n\n"
        f"Сообщение:\n{message_text}\n\n"
        f"Отправить рассылку?"
    )

    await message.answer(
        confirmation_text,
        reply_markup=get_admin_send_confirmation_keyboard()
    )

    await state.set_state(AdminManagement.admin_send_confirmation)


@router.callback_query(AdminManagement.admin_send_confirmation)
async def process_admin_send_confirmation(callback: CallbackQuery, state: FSMContext):
    """
    Подтверждение и выполнение рассылки
    """
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ У вас нет прав администратора")
        return

    if callback.data == "admin_cancel":
        await callback.message.edit_text("❌ Рассылка отменена")
        await state.clear()
        await callback.answer()
        return

    if callback.data != "admin_send_confirm":
        await callback.answer("❌ Неизвестное действие")
        return

    # Получить данные
    data = await state.get_data()
    audience_type = data.get('audience_type')
    message_text = data.get('message_text')
    class_name = data.get('class_name')

    if not audience_type or not message_text:
        await callback.message.edit_text("❌ Ошибка: данные не найдены")
        await state.clear()
        await callback.answer()
        return

    try:
        await callback.message.edit_text("⏳ Отправляю сообщения...")

        # Создать сервис рассылки
        mailing_service = MailingService(callback.bot)

        # Выполнить рассылку в зависимости от типа аудитории
        if audience_type == "all_students":
            await mailing_service.send_to_all_students(message_text)
        elif audience_type == "all_teachers":
            # TODO: Реализовать send_to_all_teachers
            await callback.message.answer("❌ Рассылка учителям пока не реализована")
        elif audience_type == "class":
            await mailing_service.send_to_class(class_name, message_text)

        await callback.message.answer("✅ Рассылка завершена! Проверьте логи для деталей.")
        await state.clear()
        await callback.answer()

    except Exception as e:
        print(f"[ERROR] Admin send failed: {e}")
        import traceback
        traceback.print_exc()
        await callback.message.answer(f"❌ Ошибка при рассылке: {e}")
        await state.clear()
        await callback.answer()
