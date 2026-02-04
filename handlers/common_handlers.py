"""
Общие handlers для всех пользователей (регистрация, /start, /help)
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext

from database.user_repository import UserRepository
from handlers.states import RegistrationStates
from keyboards.common_keyboards import get_registration_keyboard
from utils.greetings import get_greeting
from utils.config_loader import get_teacher_by_username, check_student_exists
from utils.validators import validate_full_name, normalize_full_name

# Создаем router для общих handlers
router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    Команда /start - приветствие и регистрация
    """
    user_repo = UserRepository()
    user = user_repo.get_user(message.from_user.id)

    if user:
        # Пользователь уже зарегистрирован
        text = get_greeting(message.from_user.id, message.from_user.username)
        await message.answer(text)
    else:
        # Новый пользователь - показать кнопки регистрации
        await message.answer(
            "👋 Привет! Добро пожаловать в бот табелей успеваемости Лицея ЮФУ.\n\n"
            "Выбери свою роль:",
            reply_markup=get_registration_keyboard()
        )


@router.callback_query(F.data == "register_student")
async def start_student_registration(callback: CallbackQuery, state: FSMContext):
    """
    Начало регистрации ученика
    """
    await callback.answer()
    await state.set_state(RegistrationStates.entering_name_student)
    await callback.message.edit_text(
        "👶 Регистрация ученика\n\n"
        "Напиши свое ФИО (Фамилия Имя), лицеист!\n"
        "Например: Иванов Иван"
    )


@router.callback_query(F.data == "register_teacher")
async def start_teacher_registration(callback: CallbackQuery, state: FSMContext):
    """
    Начало регистрации учителя
    """
    await callback.answer()

    username = callback.from_user.username

    # Проверка наличия username
    if not username:
        await callback.message.edit_text(
            "❌ Ошибка регистрации\n\n"
            "Для регистрации учителя необходимо установить username (имя пользователя) "
            "в настройках Telegram.\n\n"
            "📱 Как установить username:\n"
            "1. Откройте настройки Telegram\n"
            "2. Нажмите на свое имя\n"
            "3. Найдите поле \"Имя пользователя\"\n"
            "4. Установите уникальное имя (например: ivan_petrov)\n"
            "5. Вернитесь и нажмите /start снова"
        )
        await state.clear()
        return

    # Проверка что username есть в config.json
    teacher_data = get_teacher_by_username(username)
    if not teacher_data:
        await callback.message.edit_text(
            f"❌ Ошибка регистрации\n\n"
            f"Пользователь @{username} не найден в списке учителей лицея.\n\n"
            f"Если вы учитель, обратитесь к администратору бота для добавления в систему."
        )
        await state.clear()
        return

    # Сохранить в state что это учитель и его username
    await state.update_data(is_teacher=True, username=username)
    await state.set_state(RegistrationStates.entering_name_teacher)

    await callback.message.edit_text(
        "👨‍🏫 Регистрация учителя\n\n"
        "Напишите, пожалуйста, ваше ФИО (Фамилия Имя Отчество)\n"
        "Например: Иванов Иван Петрович"
    )


@router.message(RegistrationStates.entering_name_student)
async def process_student_name(message: Message, state: FSMContext):
    """
    Обработка ввода ФИО ученика
    """
    name = normalize_full_name(message.text)

    # Валидация формата
    if not validate_full_name(name):
        await message.answer(
            "❌ Некорректное ФИО\n\n"
            "Пожалуйста, введите Фамилию и Имя (минимум два слова).\n"
            "Например: Иванов Иван"
        )
        return

    # Проверка в students.json
    if not check_student_exists(name):
        await message.answer(
            "❌ Ученик не найден\n\n"
            "Вас нет в списке учеников лицея. Проверьте правильность написания ФИО "
            "или обратитесь к администратору.\n\n"
            "Формат: Фамилия Имя (с большой буквы)"
        )
        await state.clear()
        return

    # Проверка в БД (нет ли дубля)
    user_repo = UserRepository()
    if user_repo.check_name_exists(name):
        await message.answer(
            "❌ Пользователь уже зарегистрирован\n\n"
            "Пользователь с таким ФИО уже зарегистрирован в системе.\n"
            "Если это вы, используйте команду /start"
        )
        await state.clear()
        return

    # Регистрация
    success = user_repo.register_user(name, message.from_user.id, is_teacher=False)

    if success:
        print(f"[INFO] New student registered: {name} (ID: {message.from_user.id})")
        text = get_greeting(message.from_user.id)
        await message.answer(text)
    else:
        await message.answer(
            "❌ Ошибка при регистрации\n\n"
            "Произошла ошибка при сохранении данных. Попробуйте позже или обратитесь к администратору."
        )

    await state.clear()


@router.message(RegistrationStates.entering_name_teacher)
async def process_teacher_name(message: Message, state: FSMContext):
    """
    Обработка ввода ФИО учителя
    """
    name = normalize_full_name(message.text)
    data = await state.get_data()
    username = data.get('username')

    # Валидация формата
    if not validate_full_name(name):
        await message.answer(
            "❌ Некорректное ФИО\n\n"
            "Пожалуйста, введите Фамилию и Имя (минимум два слова).\n"
            "Например: Иванов Иван Петрович"
        )
        return

    # Проверка в БД (нет ли дубля)
    user_repo = UserRepository()
    if user_repo.check_name_exists(name):
        await message.answer(
            "❌ Пользователь уже зарегистрирован\n\n"
            "Пользователь с таким ФИО уже зарегистрирован в системе.\n"
            "Если это вы, используйте команду /start"
        )
        await state.clear()
        return

    # Регистрация
    success = user_repo.register_user(name, message.from_user.id, is_teacher=True)

    if success:
        print(f"[INFO] New teacher registered: {name} (@{username}, ID: {message.from_user.id})")
        text = get_greeting(message.from_user.id, username)
        await message.answer(text)
    else:
        await message.answer(
            "❌ Ошибка при регистрации\n\n"
            "Произошла ошибка при сохранении данных. Попробуйте позже или обратитесь к администратору."
        )

    await state.clear()


@router.message(F.text.in_(["ℹ️ Помощь", "/help"]))
async def cmd_help(message: Message):
    """
    Команда /help - показать список команд
    """
    user_repo = UserRepository()
    user = user_repo.get_user(message.from_user.id)

    if not user:
        # Незарегистрированный пользователь
        help_text = """
ℹ️ <b>Справка по боту табелей Лицея ЮФУ</b>

Для начала работы используйте команду /start для регистрации.

<b>Возможности бота:</b>
• Автоматическое распознавание оценок с фото журнала (для учителей)
• Получение табелей успеваемости с красивым дизайном (для учеников)
• Просмотр статистики и оценок (для учеников)
• Автоматические рассылки табелей каждые 2 недели
• Уведомления о новых оценках

Разработано для Лицея ЮФУ 🎓
        """
        await message.answer(help_text.strip())
        return

    student_name, is_teacher = user

    if is_teacher:
        # Справка для учителя
        help_text = """
ℹ️ <b>Справка для учителя</b>

<b>📸 Работа с журналом:</b>
/photo - Загрузить фото журнала для распознавания оценок
• Бот автоматически распознает оценки с помощью OCR
• Вы сможете проверить и отредактировать результаты перед сохранением

<b>📊 Статистика:</b>
/class_stats - Статистика успеваемости класса
/my_uploads - История загрузок журналов

<b>📢 Рассылка:</b>
/send_message - Отправить сообщение классу

<b>🔔 Напоминания:</b>
Каждую пятницу в 16:00 вы получите напоминание о загрузке фото журнала.

<b>ℹ️ Дополнительно:</b>
/help - Показать эту справку

По вопросам обращайтесь к администратору бота.
        """
    else:
        # Справка для ученика
        help_text = """
ℹ️ <b>Справка для ученика</b>

<b>📊 Просмотр оценок:</b>
/getcard - Получить табель успеваемости (красивое изображение)
/grades - Показать оценки текстом за полугодие
/stats - Показать статистику (средний балл, топ предметов)

<b>🎴 Табель успеваемости:</b>
Красивый табель с оценками по всем предметам за выбранный период.
Включает средний балл по каждому предмету.

<b>📈 Статистика:</b>
• Количество пятерок, четверок, троек
• Средний балл по всем предметам
• Топ-3 лучших предмета
• Предметы, требующие внимания

<b>🔔 Уведомления:</b>
• Вы получаете уведомление при появлении новых оценок
• Каждые 2 недели (воскресенье 18:00) автоматически приходит табель успеваемости

<b>ℹ️ Дополнительно:</b>
/help - Показать эту справку

Успехов в учебе! 🎓
        """

    await message.answer(help_text.strip())
