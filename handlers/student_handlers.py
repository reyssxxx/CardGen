"""
Handlers для функционала ученика
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from keyboards.student_keyboards import (
    get_student_main_menu,
    get_period_selection_keyboard,
    get_subject_filter_keyboard
)
from handlers.states import StudentGrades
from database.grade_repository import GradeRepository
from database.user_repository import UserRepository
from grade_utils import generate_grade  # Используем функцию из grade_utils.py
from utils.formatters import format_student_grades_report, format_statistics, calculate_average

# Создаем router для учеников
router = Router()

# Инициализация сервисов
grade_repo = GradeRepository()
user_repo = UserRepository()


@router.message(Command("getcard"))
async def cmd_getcard(message: Message):
    """
    Команда /getcard - получить табель успеваемости

    Использует функцию generate_grade из utils.py для генерации HTML-табеля
    """
    user_id = message.from_user.id

    # Получить пользователя
    user = user_repo.get_user(user_id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return

    student_name, is_teacher = user
    if is_teacher:
        await message.answer("❌ Эта команда доступна только ученикам")
        return

    # Проверить наличие оценок
    grades = grade_repo.get_student_grades(student_name)
    if not grades:
        await message.answer("📭 У вас пока нет оценок в системе")
        return

    # Генерировать табель
    await message.answer("⏳ Генерирую табель...")

    try:
        # Используем функцию generate_grade из utils.py
        output_file = f"data/grade_cards/табель_{student_name.replace(' ', '_')}.png"
        card_path = await generate_grade(telegram_id=user_id, output_file=output_file)

        # Отправить изображение
        photo = FSInputFile(card_path)
        await message.answer_photo(
            photo=photo,
            caption=f"📊 Табель успеваемости\n{student_name}"
        )

        print(f"[INFO] Grade card sent to {student_name}")

        # Удалить временный файл (опционально)
        # os.remove(card_path)

    except Exception as e:
        print(f"[ERROR] Failed to generate card: {e}")
        import traceback
        traceback.print_exc()
        await message.answer(f"❌ Ошибка при генерации табеля: {str(e)}")


@router.message(Command("grades"))
async def cmd_grades(message: Message):
    """
    Команда /grades - показать оценки текстом за текущий семестр (90 дней)

    Пример вывода:
    📊 Оценки для Иванов Иван:

    Математика: 5, 5, 4, 5 (средний: 4.75)
    Физика: 4, 5, 4 (средний: 4.33)
    Русский язык: 5, 5, 5, 4 (средний: 4.75)
    ...
    """
    user_id = message.from_user.id

    # Получить пользователя
    user = user_repo.get_user(user_id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return

    student_name, is_teacher = user
    if is_teacher:
        await message.answer("❌ Эта команда доступна только ученикам")
        return

    # Получить оценки за полугодие (90 дней)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    grades = grade_repo.get_student_grades(
        student_name=student_name,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )

    if not grades:
        await message.answer("📭 У вас пока нет оценок за этот период")
        return

    # Сгруппировать по предметам
    grades_by_subject = {}
    for grade in grades:
        subject = grade['subject']
        if subject not in grades_by_subject:
            grades_by_subject[subject] = []
        grades_by_subject[subject].append(grade['grade'])

    # Форматировать отчет
    report = format_student_grades_report(student_name, grades_by_subject)

    await message.answer(report)


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """
    Команда /stats - показать статистику оценок

    Пример вывода:
    📈 Статистика оценок:

    Пятерки: 15
    Четверки: 8
    Тройки: 2
    Двойки: 0

    💯 Средний балл: 4.56

    📝 Всего оценок: 25

    🏆 Лучшие предметы:
    1. Информатика (5.0)
    2. Математика (4.9)
    3. Физика (4.7)

    ⚠️ Требуют внимания:
    1. Русский язык (3.5)
    """
    user_id = message.from_user.id

    # Получить пользователя
    user = user_repo.get_user(user_id)
    if not user:
        await message.answer("❌ Вы не зарегистрированы. Используйте /start")
        return

    student_name, is_teacher = user
    if is_teacher:
        await message.answer("❌ Эта команда доступна только ученикам")
        return

    # Получить оценки за полугодие
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    grades = grade_repo.get_student_grades(
        student_name=student_name,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )

    if not grades:
        await message.answer("📭 У вас пока нет оценок за этот период")
        return

    # Собрать статистику
    grade_counts = {'5': 0, '4': 0, '3': 0, '2': 0}
    grades_by_subject = {}

    for grade in grades:
        # Подсчет по типам
        if grade['grade'] in grade_counts:
            grade_counts[grade['grade']] += 1

        # Группировка по предметам
        subject = grade['subject']
        if subject not in grades_by_subject:
            grades_by_subject[subject] = []
        if grade['grade'] in ['2', '3', '4', '5']:
            grades_by_subject[subject].append(grade['grade'])

    # Средний балл
    avg = grade_repo.get_average_grade(student_name)

    # Топ-3 предмета
    subject_averages = {}
    for subject, subject_grades in grades_by_subject.items():
        if subject_grades:
            subject_averages[subject] = calculate_average(subject_grades)

    sorted_subjects = sorted(subject_averages.items(), key=lambda x: x[1], reverse=True)
    top_3 = sorted_subjects[:3]
    bottom_3 = sorted_subjects[-3:] if len(sorted_subjects) > 3 else []

    # Форматировать
    stats = {
        'grade_counts': grade_counts,
        'average_grade': round(avg, 2) if avg else 0,
        'total_grades': len(grades)
    }

    report_lines = [format_statistics(stats)]

    if top_3:
        report_lines.append("\n🏆 Лучшие предметы:")
        for i, (subject, avg_grade) in enumerate(top_3, 1):
            report_lines.append(f"{i}. {subject} ({avg_grade})")

    if bottom_3 and len(sorted_subjects) > 3:
        report_lines.append("\n⚠️ Требуют внимания:")
        for i, (subject, avg_grade) in enumerate(bottom_3, 1):
            report_lines.append(f"{i}. {subject} ({avg_grade})")

    await message.answer('\n'.join(report_lines))


@router.message(F.text == "📊 Мои оценки")
async def button_grades(message: Message):
    """Обработчик кнопки 'Мои оценки' из главного меню"""
    await cmd_grades(message)


@router.message(F.text == "🎴 Получить табель")
async def button_getcard(message: Message):
    """Обработчик кнопки 'Получить табель' из главного меню"""
    await cmd_getcard(message)


@router.message(F.text == "📈 Статистика")
async def button_stats(message: Message):
    """Обработчик кнопки 'Статистика' из главного меню"""
    await cmd_stats(message)


@router.message(F.text == "ℹ️ Помощь")
async def button_help(message: Message):
    """Обработчик кнопки 'Помощь' из главного меню"""
    help_text = """
📚 Доступные команды для учеников:

/getcard - Получить табель успеваемости за последние 14 дней
/grades - Показать оценки текстом за полугодие
/stats - Показать статистику оценок

Или используйте кнопки меню ниже.
    """
    await message.answer(help_text.strip())
