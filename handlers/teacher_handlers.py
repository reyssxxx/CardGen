"""
Handlers для функционала учителя
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from keyboards.teacher_keyboards import (
    get_subject_selection_keyboard,
    get_class_selection_keyboard,
    get_date_review_keyboard,
    get_student_review_keyboard,
    get_grade_edit_keyboard,
    get_final_confirmation_keyboard,
    get_teacher_main_menu
)
from handlers.states import TeacherPhotoUpload, TeacherManualGrade, TeacherSendMessage
from utils.config_loader import get_teacher_by_username, get_students_by_class, get_all_classes
from utils.validators import validate_date, parse_date_with_year
from utils.formatters import format_date, format_grades_list
from services.ocr_pipeline import process_journal_photo
from services.notification_service import NotificationService
from database.grade_repository import GradeRepository
from database.photo_repository import PhotoRepository

# Создаем router для учителей
router = Router()

# Инициализация репозиториев
grade_repo = GradeRepository()
photo_repo = PhotoRepository()


@router.message(Command("photo"))
async def cmd_photo(message: Message, state: FSMContext):
    """
    Команда /photo - начать загрузку фото журнала
    """
    username = message.from_user.username

    if not username:
        await message.answer(
            "❌ Для использования этой функции необходимо установить username в настройках Telegram."
        )
        return

    # Проверка что пользователь - учитель
    teacher_data = get_teacher_by_username(username)
    if not teacher_data:
        await message.answer(
            "❌ Вы не зарегистрированы как учитель.\n"
            "Обратитесь к администратору."
        )
        return

    # Получаем список предметов учителя
    subjects = []
    if len(teacher_data) > 1 and teacher_data[1]:
        subjects = [s.strip() for s in teacher_data[1].split(',')]

    if not subjects:
        await message.answer(
            "❌ У вас не указаны предметы. Обратитесь к администратору."
        )
        return

    # Сохраняем данные учителя в состояние
    await state.update_data(
        teacher_username=username,
        teacher_data=teacher_data,
        subjects=subjects
    )

    # Показываем выбор предмета
    await message.answer(
        "📸 Загрузка фото журнала\n\n"
        "Шаг 1 из 3: Выберите предмет",
        reply_markup=get_subject_selection_keyboard(subjects)
    )

    await state.set_state(TeacherPhotoUpload.waiting_for_subject)


@router.callback_query(TeacherPhotoUpload.waiting_for_subject, F.data.startswith("subject:"))
async def process_subject_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора предмета
    """
    await callback.answer()

    subject = callback.data.split(":", 1)[1]
    await state.update_data(subject=subject)

    # Получаем список всех классов
    all_classes = get_all_classes()

    if not all_classes:
        await callback.message.edit_text(
            "❌ Не найдено ни одного класса в конфигурации.\n"
            "Обратитесь к администратору."
        )
        await state.clear()
        return

    # Показываем выбор класса (с автоопределением)
    await callback.message.edit_text(
        f"📸 Загрузка фото журнала\n"
        f"Предмет: {subject}\n\n"
        f"Шаг 2 из 3: Выберите класс или разрешите автоопределение",
        reply_markup=get_class_selection_keyboard(all_classes, allow_auto_detect=True)
    )

    await state.set_state(TeacherPhotoUpload.waiting_for_class)


@router.callback_query(TeacherPhotoUpload.waiting_for_class, F.data.startswith("class:"))
async def process_class_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора класса
    """
    await callback.answer()

    class_choice = callback.data.split(":", 1)[1]

    if class_choice == "auto":
        # Автоопределение класса
        await state.update_data(expected_class=None, auto_detect_class=True)
        class_text = "автоопределение"
    else:
        await state.update_data(expected_class=class_choice, auto_detect_class=False)
        class_text = class_choice

    data = await state.get_data()
    subject = data['subject']

    await callback.message.edit_text(
        f"📸 Загрузка фото журнала\n"
        f"Предмет: {subject}\n"
        f"Класс: {class_text}\n\n"
        f"Шаг 3 из 3: Отправьте фотографию журнала\n\n"
        f"Рекомендации для лучшего распознавания:\n"
        f"• Сфотографируйте журнал при хорошем освещении\n"
        f"• Избегайте бликов и теней\n"
        f"• Расположите камеру параллельно странице\n"
        f"• Убедитесь что текст четкий и читаемый"
    )

    await state.set_state(TeacherPhotoUpload.waiting_for_photo)


@router.message(TeacherPhotoUpload.waiting_for_photo, F.photo)
async def process_photo_upload(message: Message, state: FSMContext):
    """
    Обработка загруженного фото
    """
    # Получаем фото максимального качества
    photo = message.photo[-1]

    data = await state.get_data()
    teacher_username = data['teacher_username']
    subject = data['subject']
    expected_class = data.get('expected_class')

    # Создаем директорию для фото если не существует
    upload_dir = Path("data/uploaded_photos")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Генерируем уникальное имя файла (без кириллицы для совместимости с OpenCV)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Используем только timestamp и username, без названия предмета (из-за кириллицы)
    filename = f"{teacher_username}_{timestamp}.jpg"
    file_path = upload_dir / filename

    # Скачиваем фото
    await message.bot.download(photo, destination=file_path)

    # Записываем в БД факт загрузки
    upload_id = photo_repo.add_upload(
        teacher_username=teacher_username,
        subject=subject,
        class_name=expected_class or "auto",
        file_path=str(file_path)
    )

    await state.update_data(
        photo_path=str(file_path),
        upload_id=upload_id
    )

    # Показываем статус обработки
    processing_msg = await message.answer(
        "⏳ Обрабатываю фотографию...\n\n"
        "Это может занять 10-30 секунд в зависимости от качества изображения."
    )

    # Запускаем OCR обработку
    try:
        # Получаем список учеников для валидации (если класс известен)
        students_list = None
        if expected_class:
            students_list = get_students_by_class(expected_class)

        # Запускаем пайплайн OCR
        result = process_journal_photo(
            image_path=str(file_path),
            subject=subject,
            teacher_username=teacher_username,
            students_list=students_list,
            expected_class=expected_class,
            save_debug=False
        )

        # Обновляем статус загрузки
        if result.get('success'):
            photo_repo.update_status(upload_id, 'processed')
        else:
            photo_repo.update_status(upload_id, 'error', error_message=result.get('error'))

        await processing_msg.delete()

        if not result.get('success'):
            await message.answer(
                f"❌ Ошибка при обработке изображения:\n\n"
                f"{result.get('error', 'Неизвестная ошибка')}\n\n"
                f"Попробуйте сфотографировать журнал еще раз при лучшем освещении."
            )
            await state.clear()
            return

        # Сохраняем результаты OCR в состояние
        ocr_result = result['ocr_result']
        db_data = result['db_data']
        warnings = result.get('warnings', [])

        await state.update_data(
            ocr_result=ocr_result,
            db_data=db_data,
            warnings=warnings,
            detected_class=ocr_result.get('class'),
            dates=ocr_result.get('dates', []),
            students=ocr_result.get('students', [])
        )

        # Показываем результаты распознавания
        detected_class = ocr_result.get('class', 'не определен')
        dates = ocr_result.get('dates', [])
        students = ocr_result.get('students', [])

        # Определяем качество распознавания
        quality_emoji = "✅" if len(students) > 5 and not warnings else "⚠️"

        summary_text = (
            f"{quality_emoji} Фото обработано!\n\n"
            f"📋 Результаты распознавания:\n"
            f"• Класс: {detected_class}\n"
            f"• Обнаружено дат: {len(dates)}\n"
            f"• Обнаружено учеников: {len(students)}\n"
        )

        if warnings:
            summary_text += f"\n⚠️ Предупреждения ({len(warnings)}):\n"
            for warning in warnings[:3]:  # Показываем только первые 3
                summary_text += f"• {warning}\n"

        if len(students) < 5:
            summary_text += "\n💡 Совет: Если распознано мало учеников, попробуйте:\n"
            summary_text += "• Сфотографировать при лучшем освещении\n"
            summary_text += "• Убедиться что камера параллельна странице\n"
            summary_text += "• Использовать /add_grade для ручного ввода\n"

        summary_text += "\nТеперь проверим распознанные данные."

        await message.answer(summary_text)

        # Переходим к проверке дат
        await show_dates_review(message, state)

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[ERROR] OCR processing failed:\n{error_details}")

        # Пытаемся удалить сообщение об обработке
        try:
            await processing_msg.delete()
        except Exception:
            pass  # Сообщение уже удалено или недоступно

        photo_repo.update_status(upload_id, 'error', error_message=str(e))

        await message.answer(
            f"❌ Произошла ошибка при обработке:\n\n"
            f"{str(e)}\n\n"
            f"Попробуйте еще раз или обратитесь к администратору."
        )
        await state.clear()


async def show_dates_review(message: Message, state: FSMContext):
    """
    Показать распознанные даты для проверки
    """
    data = await state.get_data()
    dates = data.get('dates', [])

    if not dates:
        # Если дат нет, пропускаем этап
        await message.answer(
            "⚠️ Даты не были распознаны.\n"
            "Вы сможете отредактировать оценки вручную."
        )
        await show_students_review(message, state, student_index=0)
        return

    # Форматируем даты для отображения
    dates_text = "📅 Распознанные даты:\n\n"
    for idx, date in enumerate(dates, 1):
        formatted_date = format_date(date, '%d.%m.%Y', '%d.%m.%Y')
        dates_text += f"{idx}. {formatted_date}\n"

    dates_text += "\nВсе даты верны?"

    await message.answer(
        dates_text,
        reply_markup=get_date_review_keyboard(len(dates))
    )

    await state.set_state(TeacherPhotoUpload.reviewing_dates)


@router.callback_query(TeacherPhotoUpload.reviewing_dates, F.data == "dates_confirmed")
async def dates_confirmed(callback: CallbackQuery, state: FSMContext):
    """
    Даты подтверждены, переходим к проверке оценок
    """
    await callback.answer("✅ Даты подтверждены")
    await callback.message.delete()

    await show_students_review(callback.message, state, student_index=0)


@router.callback_query(TeacherPhotoUpload.reviewing_dates, F.data.startswith("edit_date:"))
async def edit_date(callback: CallbackQuery, state: FSMContext):
    """
    Редактирование конкретной даты
    """
    date_idx = int(callback.data.split(":")[1])

    await state.update_data(editing_date_index=date_idx)

    data = await state.get_data()
    dates = data.get('dates', [])

    if date_idx >= len(dates):
        await callback.answer("❌ Ошибка: неверный индекс даты")
        return

    current_date = dates[date_idx]
    formatted_date = format_date(current_date, '%d.%m.%Y', '%d.%m.%Y')

    await callback.message.edit_text(
        f"✏️ Редактирование даты {date_idx + 1}\n\n"
        f"Текущее значение: {formatted_date}\n\n"
        f"Введите новую дату в формате ДД.ММ.ГГГГ или ДД.ММ\n"
        f"Например: 01.09.2026 или 01.09"
    )

    await state.set_state(TeacherPhotoUpload.editing_date)


@router.message(TeacherPhotoUpload.editing_date)
async def save_edited_date(message: Message, state: FSMContext):
    """
    Сохранение отредактированной даты
    """
    new_date_str = message.text.strip()

    # Валидация и парсинг даты
    if not validate_date(new_date_str):
        await message.answer(
            "❌ Неверный формат даты.\n"
            "Используйте формат ДД.ММ.ГГГГ или ДД.ММ"
        )
        return

    # Парсим дату с добавлением года если нужно
    full_date = parse_date_with_year(new_date_str)

    data = await state.get_data()
    dates = data.get('dates', [])
    date_idx = data.get('editing_date_index')

    # Обновляем дату
    dates[date_idx] = full_date
    await state.update_data(dates=dates)

    # Также обновляем в db_data если есть
    db_data = data.get('db_data')
    if db_data:
        db_data['dates'][date_idx] = full_date
        await state.update_data(db_data=db_data)

    await message.answer(f"✅ Дата обновлена: {full_date}")

    # Возвращаемся к просмотру дат
    await show_dates_review(message, state)


async def show_students_review(message: Message, state: FSMContext, student_index: int):
    """
    Показать оценки ученика для проверки/редактирования
    """
    data = await state.get_data()
    students = data.get('students', [])
    dates = data.get('dates', [])

    if not students:
        await message.answer("❌ Ученики не обнаружены.")
        await state.clear()
        return

    if student_index >= len(students):
        # Все ученики проверены, показываем финальное подтверждение
        await show_final_confirmation(message, state)
        return

    student_data = students[student_index]
    student_name = student_data['name']
    grades_row = student_data.get('grades_row', [])

    # Форматируем оценки
    grades_text = f"👤 {student_name}\n\n"

    if dates and len(dates) == len(grades_row):
        for idx, (date, grade) in enumerate(zip(dates, grades_row)):
            formatted_date = format_date(date, '%d.%m.%Y', '%d.%m')
            grade_display = grade if grade else '-'
            grades_text += f"{formatted_date}: {grade_display}\n"
    elif grades_row:
        grades_text += "Оценки: " + format_grades_list(grades_row)
    else:
        grades_text += "⚠️ Оценки не распознаны\n"
        grades_text += "Вы можете отменить загрузку и добавить оценки вручную через /add_grade\n"

    grades_text += f"\n📊 Ученик {student_index + 1} из {len(students)}"

    is_last_student = (student_index == len(students) - 1)

    await message.answer(
        grades_text,
        reply_markup=get_student_review_keyboard(student_index, len(dates), is_last_student)
    )

    await state.set_state(TeacherPhotoUpload.reviewing_students)
    await state.update_data(current_student_index=student_index)


@router.callback_query(TeacherPhotoUpload.reviewing_students, F.data.startswith("review_student:"))
async def navigate_student(callback: CallbackQuery, state: FSMContext):
    """
    Навигация между учениками
    """
    student_idx = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.delete()

    await show_students_review(callback.message, state, student_idx)


@router.callback_query(TeacherPhotoUpload.reviewing_students, F.data.startswith("review_edit:"))
async def review_edit_grade(callback: CallbackQuery, state: FSMContext):
    """
    Начать редактирование оценки
    """
    parts = callback.data.split(":")
    student_idx = int(parts[1])
    date_idx = int(parts[2])

    data = await state.get_data()
    students = data.get('students', [])
    dates = data.get('dates', [])

    student_name = students[student_idx]['name']
    current_grade = students[student_idx]['grades_row'][date_idx] if date_idx < len(students[student_idx]['grades_row']) else None
    date_str = format_date(dates[date_idx], '%d.%m.%Y', '%d.%m') if date_idx < len(dates) else f"Столбец {date_idx + 1}"

    await callback.message.edit_text(
        f"✏️ Редактирование оценки\n\n"
        f"Ученик: {student_name}\n"
        f"Дата: {date_str}\n"
        f"Текущая оценка: {current_grade if current_grade else 'нет'}\n\n"
        f"Выберите новую оценку:",
        reply_markup=get_grade_edit_keyboard(student_idx, date_idx)
    )

    await state.set_state(TeacherPhotoUpload.editing_grade)


@router.callback_query(TeacherPhotoUpload.editing_grade, F.data.startswith("edit_grade:"))
async def save_edited_grade(callback: CallbackQuery, state: FSMContext):
    """
    Сохранение отредактированной оценки
    """
    parts = callback.data.split(":")
    student_idx = int(parts[1])
    date_idx = int(parts[2])
    new_grade = parts[3]

    data = await state.get_data()
    students = data.get('students', [])

    # Обновляем оценку
    if new_grade == "delete":
        students[student_idx]['grades_row'][date_idx] = None
        await callback.answer("🗑 Оценка удалена")
    else:
        students[student_idx]['grades_row'][date_idx] = new_grade
        await callback.answer(f"✅ Оценка изменена на {new_grade}")

    await state.update_data(students=students)

    # Также обновляем в db_data для последующего сохранения
    await update_db_data_after_edit(state, student_idx, date_idx, new_grade)

    await callback.message.delete()

    # Возвращаемся к просмотру этого ученика
    await show_students_review(callback.message, state, student_idx)


async def update_db_data_after_edit(state: FSMContext, student_idx: int, date_idx: int, new_grade: str):
    """
    Обновить db_data после редактирования оценки
    """
    data = await state.get_data()
    db_data = data.get('db_data')
    students = data.get('students', [])
    dates = data.get('dates', [])

    if not db_data:
        return

    student_name = students[student_idx]['name']
    date = dates[date_idx] if date_idx < len(dates) else None

    if not date:
        return

    # Ищем и обновляем или удаляем запись в grades_data
    grades_data = db_data.get('grades_data', [])

    # Удаляем старую запись для этого ученика и даты
    grades_data = [g for g in grades_data if not (g['student_name'] == student_name and g['date'] == date)]

    # Добавляем новую запись если оценка не удалена
    if new_grade != "delete" and new_grade is not None:
        grades_data.append({
            'student_name': student_name,
            'class': db_data['class'],
            'subject': db_data['subject'],
            'grade': new_grade,
            'date': date,
            'teacher_username': db_data['teacher_username']
        })

    db_data['grades_data'] = grades_data
    await state.update_data(db_data=db_data)


@router.callback_query(TeacherPhotoUpload.reviewing_students, F.data.startswith("confirm_student:"))
async def confirm_student(callback: CallbackQuery, state: FSMContext):
    """
    Подтверждение оценок ученика, переход к следующему
    """
    student_idx = int(callback.data.split(":")[1])
    await callback.answer("✅ Оценки подтверждены")
    await callback.message.delete()

    # Переходим к следующему ученику
    await show_students_review(callback.message, state, student_idx + 1)


async def show_final_confirmation(message: Message, state: FSMContext):
    """
    Финальное подтверждение перед сохранением в БД
    """
    data = await state.get_data()
    db_data = data.get('db_data', {})
    warnings = data.get('warnings', [])

    grades_count = len(db_data.get('grades_data', []))
    detected_class = db_data.get('class', 'не определен')
    subject = db_data.get('subject', '')

    summary = (
        f"📊 Итоговая сводка\n\n"
        f"Класс: {detected_class}\n"
        f"Предмет: {subject}\n"
        f"Всего оценок для сохранения: {grades_count}\n"
    )

    if warnings:
        summary += f"\n⚠️ Предупреждений: {len(warnings)}\n"

    summary += "\nСохранить все оценки в базу данных?"

    await message.answer(
        summary,
        reply_markup=get_final_confirmation_keyboard()
    )

    await state.set_state(TeacherPhotoUpload.final_confirmation)


@router.callback_query(TeacherPhotoUpload.final_confirmation, F.data == "save_grades")
async def save_grades_to_db(callback: CallbackQuery, state: FSMContext):
    """
    Сохранение всех оценок в БД
    """
    await callback.answer()

    data = await state.get_data()
    db_data = data.get('db_data', {})
    upload_id = data.get('upload_id')
    photo_path = data.get('photo_path')

    grades_data = db_data.get('grades_data', [])

    if not grades_data:
        await callback.message.edit_text(
            "❌ Нет оценок для сохранения."
        )
        await state.clear()
        return

    try:
        # Сохраняем оценки в БД (bulk insert)
        saved_count = grade_repo.add_grades_bulk(grades_data)

        # Обновляем статус загрузки
        if upload_id:
            photo_repo.update_status(upload_id, 'completed')

        # Удаляем фото (согласно требованиям)
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
            print(f"[INFO] Deleted photo: {photo_path}")

        await callback.message.edit_text(
            f"✅ Оценки успешно сохранены!\n\n"
            f"Добавлено оценок: {saved_count}\n"
            f"Класс: {db_data['class']}\n"
            f"Предмет: {db_data['subject']}\n\n"
            f"Ученики получат уведомления о новых оценках."
        )

        # Отправить уведомления ученикам о новых оценках
        try:
            notification_service = NotificationService(callback.bot)
            await notification_service.notify_students_new_grades(grades_data)
            print(f"[INFO] Sent grade notifications for {len(grades_data)} grades")
        except Exception as notification_error:
            print(f"[ERROR] Failed to send grade notifications: {notification_error}")
            # Не прерываем выполнение, оценки уже сохранены

    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при сохранении оценок:\n\n{str(e)}\n\n"
            f"Обратитесь к администратору."
        )

    finally:
        await state.clear()


@router.callback_query(TeacherPhotoUpload.final_confirmation, F.data == "continue_editing")
async def continue_editing(callback: CallbackQuery, state: FSMContext):
    """
    Продолжить редактирование
    """
    await callback.answer()
    await callback.message.delete()

    # Возвращаемся к первому ученику
    await show_students_review(callback.message, state, student_index=0)


@router.callback_query(F.data == "cancel")
@router.callback_query(TeacherPhotoUpload.final_confirmation, F.data == "cancel_all")
async def cancel_upload(callback: CallbackQuery, state: FSMContext):
    """
    Отмена загрузки
    """
    await callback.answer("❌ Отменено")

    data = await state.get_data()
    photo_path = data.get('photo_path')
    upload_id = data.get('upload_id')

    # Удаляем фото если загружено
    if photo_path and os.path.exists(photo_path):
        os.remove(photo_path)

    # Обновляем статус
    if upload_id:
        photo_repo.update_status(upload_id, 'cancelled')

    await callback.message.edit_text(
        "❌ Загрузка отменена."
    )

    await state.clear()


@router.message(Command("teacher_menu"))
async def show_teacher_menu(message: Message):
    """
    Показать главное меню учителя
    """
    username = message.from_user.username

    if not username:
        await message.answer("❌ Необходим username в настройках Telegram.")
        return

    teacher_data = get_teacher_by_username(username)
    if not teacher_data:
        await message.answer("❌ Вы не зарегистрированы как учитель.")
        return

    await message.answer(
        f"👨‍🏫 Меню учителя\n\n"
        f"Выберите действие:",
        reply_markup=get_teacher_main_menu()
    )


# ==================== Reply Keyboard Button Handlers ====================

@router.message(F.text == "📸 Загрузить фото журнала")
async def reply_button_photo(message: Message, state: FSMContext):
    """
    Reply кнопка для загрузки фото - перенаправляет на /photo
    """
    await cmd_photo(message, state)


@router.message(F.text == "✏️ Добавить оценку вручную")
async def reply_button_add_grade(message: Message, state: FSMContext):
    """
    Reply кнопка для ручного добавления оценки - перенаправляет на /add_grade
    """
    await cmd_add_grade(message, state)


@router.message(F.text == "📊 Мои статистика")
async def reply_button_stats(message: Message):
    """
    Reply кнопка для статистики учителя
    """
    await message.answer(
        "📊 Статистика в разработке.\n\n"
        "Здесь будет отображаться:\n"
        "• Количество выставленных оценок\n"
        "• Средний балл по предметам\n"
        "• История загрузок"
    )


@router.message(F.text == "👥 Список учеников")
async def reply_button_students(message: Message):
    """
    Reply кнопка для просмотра списка учеников
    """
    username = message.from_user.username

    if not username:
        await message.answer("❌ Необходим username в настройках Telegram.")
        return

    teacher_data = get_teacher_by_username(username)
    if not teacher_data:
        await message.answer("❌ Вы не зарегистрированы как учитель.")
        return

    # Получаем классы учителя
    teacher_classes = []
    if len(teacher_data) > 2 and teacher_data[2]:
        teacher_classes = [c.strip() for c in teacher_data[2].split(',')]

    if not teacher_classes:
        await message.answer("❌ У вас не указаны классы. Обратитесь к администратору.")
        return

    # Собираем учеников по классам
    students_text = "👥 Список учеников\n\n"
    for class_name in teacher_classes:
        students = get_students_by_class(class_name)
        if students:
            students_text += f"📚 {class_name}:\n"
            for student in students:
                students_text += f"  • {student}\n"
            students_text += "\n"

    await message.answer(students_text)


@router.message(F.text == "📢 Отправить сообщение классу")
async def reply_button_send_message(message: Message, state: FSMContext):
    """
    Reply кнопка для отправки сообщения классу
    """
    username = message.from_user.username

    if not username:
        await message.answer("❌ Необходим username в настройках Telegram.")
        return

    teacher_data = get_teacher_by_username(username)
    if not teacher_data:
        await message.answer("❌ Вы не зарегистрированы как учитель.")
        return

    # Получаем классы учителя
    teacher_classes = []
    if len(teacher_data) > 2 and teacher_data[2]:
        teacher_classes = [c.strip() for c in teacher_data[2].split(',')]

    if not teacher_classes:
        await message.answer("❌ У вас не указаны классы. Обратитесь к администратору.")
        return

    # Сохраняем данные учителя
    await state.update_data(
        teacher_username=username,
        teacher_classes=teacher_classes
    )

    # Показываем выбор класса
    await message.answer(
        "📢 Отправка сообщения классу\n\n"
        "Шаг 1 из 2: Выберите класс",
        reply_markup=get_class_selection_keyboard(teacher_classes, allow_auto_detect=False)
    )

    await state.set_state(TeacherSendMessage.waiting_for_class)


@router.callback_query(TeacherSendMessage.waiting_for_class, F.data.startswith("class:"))
async def send_message_class_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора класса для отправки сообщения
    """
    await callback.answer()

    class_name = callback.data.split(":", 1)[1]
    await state.update_data(class_name=class_name)

    # Получаем учеников класса
    students = get_students_by_class(class_name)

    if not students:
        await callback.message.edit_text(
            f"❌ В классе {class_name} не найдено учеников.\n"
            "Обратитесь к администратору."
        )
        await state.clear()
        return

    await callback.message.edit_text(
        f"📢 Отправка сообщения классу {class_name}\n\n"
        f"📊 Сообщение получат {len(students)} учеников\n\n"
        f"Шаг 2 из 2: Введите текст сообщения"
    )

    await state.set_state(TeacherSendMessage.waiting_for_message)


@router.message(TeacherSendMessage.waiting_for_message)
async def send_message_text_input(message: Message, state: FSMContext):
    """
    Обработка ввода текста сообщения и отправка
    """
    message_text = message.text.strip()

    if len(message_text) < 5:
        await message.answer("❌ Сообщение слишком короткое. Минимум 5 символов.")
        return

    if len(message_text) > 4000:
        await message.answer("❌ Сообщение слишком длинное. Максимум 4000 символов.")
        return

    data = await state.get_data()
    class_name = data['class_name']
    teacher_username = data['teacher_username']

    # Получаем учеников класса с их user_id
    from database.user_repository import UserRepository
    user_repo = UserRepository()

    students = get_students_by_class(class_name)

    # Отправляем сообщение
    sent_count = 0
    failed_count = 0

    processing_msg = await message.answer(
        f"📤 Отправка сообщения {len(students)} ученикам класса {class_name}..."
    )

    for student_name in students:
        try:
            # Находим пользователя по имени
            user = user_repo.get_user_by_name(student_name)

            if user and user['role'] == 'student':
                # Формируем сообщение
                full_message = (
                    f"📢 Сообщение от учителя\n\n"
                    f"{message_text}\n\n"
                    f"—\n"
                    f"👨‍🏫 Учитель: @{teacher_username}"
                )

                # Отправляем через бота
                await message.bot.send_message(
                    chat_id=user['ID'],
                    text=full_message
                )
                sent_count += 1
                print(f"[INFO] Message sent to {student_name} (ID: {user['ID']})")

            else:
                print(f"[WARNING] Student {student_name} not found in database or not a student")
                failed_count += 1

        except Exception as e:
            print(f"[ERROR] Failed to send message to {student_name}: {e}")
            failed_count += 1

    # Удаляем сообщение о процессе
    try:
        await processing_msg.delete()
    except Exception:
        pass

    # Показываем результат
    result_text = f"✅ Сообщение отправлено!\n\n"
    result_text += f"📊 Статистика:\n"
    result_text += f"• Успешно отправлено: {sent_count}\n"

    if failed_count > 0:
        result_text += f"• Не удалось отправить: {failed_count}\n"
        result_text += f"\n⚠️ Некоторые ученики могут не быть зарегистрированы в боте."

    result_text += f"\n\n📝 Отправленное сообщение:\n{message_text[:200]}"
    if len(message_text) > 200:
        result_text += "..."

    await message.answer(result_text)

    await state.clear()


# ==================== /add_grade Command ====================

@router.message(Command("add_grade"))
async def cmd_add_grade(message: Message, state: FSMContext):
    """
    Команда /add_grade - добавить оценку вручную
    """
    username = message.from_user.username

    if not username:
        await message.answer(
            "❌ Для использования этой функции необходимо установить username в настройках Telegram."
        )
        return

    # Проверка что пользователь - учитель
    teacher_data = get_teacher_by_username(username)
    if not teacher_data:
        await message.answer(
            "❌ Вы не зарегистрированы как учитель.\n"
            "Обратитесь к администратору."
        )
        return

    # Получаем список предметов учителя
    subjects = []
    if len(teacher_data) > 1 and teacher_data[1]:
        subjects = [s.strip() for s in teacher_data[1].split(',')]

    if not subjects:
        await message.answer(
            "❌ У вас не указаны предметы. Обратитесь к администратору."
        )
        return

    # Сохраняем данные учителя в состояние
    await state.update_data(
        teacher_username=username,
        teacher_data=teacher_data,
        subjects=subjects
    )

    # Показываем выбор предмета
    await message.answer(
        "✏️ Добавление оценки вручную\n\n"
        "Шаг 1 из 5: Выберите предмет",
        reply_markup=get_subject_selection_keyboard(subjects)
    )

    await state.set_state(TeacherManualGrade.waiting_for_subject)


@router.callback_query(TeacherManualGrade.waiting_for_subject, F.data.startswith("subject:"))
async def manual_subject_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора предмета для ручного добавления
    """
    await callback.answer()

    subject = callback.data.split(":", 1)[1]
    await state.update_data(subject=subject)

    # Получаем список всех классов
    all_classes = get_all_classes()

    if not all_classes:
        await callback.message.edit_text(
            "❌ Не найдено ни одного класса в конфигурации.\n"
            "Обратитесь к администратору."
        )
        await state.clear()
        return

    # Показываем выбор класса (без автоопределения)
    await callback.message.edit_text(
        f"✏️ Добавление оценки вручную\n"
        f"Предмет: {subject}\n\n"
        f"Шаг 2 из 5: Выберите класс",
        reply_markup=get_class_selection_keyboard(all_classes, allow_auto_detect=False)
    )

    await state.set_state(TeacherManualGrade.waiting_for_class)


@router.callback_query(TeacherManualGrade.waiting_for_class, F.data.startswith("class:"))
async def manual_class_selection(callback: CallbackQuery, state: FSMContext):
    """
    Обработка выбора класса для ручного добавления
    """
    await callback.answer()

    class_name = callback.data.split(":", 1)[1]
    await state.update_data(class_name=class_name)

    # Получаем список учеников класса
    students = get_students_by_class(class_name)

    if not students:
        await callback.message.edit_text(
            f"❌ В классе {class_name} не найдено учеников.\n"
            "Обратитесь к администратору."
        )
        await state.clear()
        return

    data = await state.get_data()
    subject = data['subject']

    # Формируем текст со списком учеников
    students_list_text = "\n".join([f"{i+1}. {name}" for i, name in enumerate(students)])

    await callback.message.edit_text(
        f"✏️ Добавление оценки вручную\n"
        f"Предмет: {subject}\n"
        f"Класс: {class_name}\n\n"
        f"Шаг 3 из 5: Введите ФИ ученика\n\n"
        f"Список учеников класса:\n{students_list_text}\n\n"
        f"Введите фамилию и имя ученика (например: Иванов Иван)"
    )

    await state.update_data(students_list=students)
    await state.set_state(TeacherManualGrade.waiting_for_student)


@router.message(TeacherManualGrade.waiting_for_student)
async def manual_student_name_input(message: Message, state: FSMContext):
    """
    Обработка ввода имени ученика
    """
    student_name = message.text.strip()

    data = await state.get_data()
    students_list = data.get('students_list', [])

    # Проверяем что ученик есть в списке
    if student_name not in students_list:
        await message.answer(
            f"❌ Ученик '{student_name}' не найден в списке.\n\n"
            f"Проверьте правильность написания или выберите из списка выше."
        )
        return

    await state.update_data(student_name=student_name)

    subject = data['subject']
    class_name = data['class_name']

    await message.answer(
        f"✏️ Добавление оценки вручную\n"
        f"Предмет: {subject}\n"
        f"Класс: {class_name}\n"
        f"Ученик: {student_name}\n\n"
        f"Шаг 4 из 5: Введите дату\n\n"
        f"Формат: ДД.ММ.ГГГГ или ДД.ММ\n"
        f"Например: 03.02.2026 или 03.02"
    )

    await state.set_state(TeacherManualGrade.waiting_for_date)


@router.message(TeacherManualGrade.waiting_for_date)
async def manual_date_input(message: Message, state: FSMContext):
    """
    Обработка ввода даты
    """
    date_str = message.text.strip()

    # Валидация даты
    if not validate_date(date_str):
        await message.answer(
            "❌ Неверный формат даты.\n\n"
            "Используйте формат ДД.ММ.ГГГГ или ДД.ММ\n"
            "Например: 03.02.2026 или 03.02"
        )
        return

    # Парсим дату с добавлением года если нужно
    full_date = parse_date_with_year(date_str)
    await state.update_data(date=full_date)

    data = await state.get_data()
    subject = data['subject']
    class_name = data['class_name']
    student_name = data['student_name']

    await message.answer(
        f"✏️ Добавление оценки вручную\n"
        f"Предмет: {subject}\n"
        f"Класс: {class_name}\n"
        f"Ученик: {student_name}\n"
        f"Дата: {full_date}\n\n"
        f"Шаг 5 из 5: Введите оценку\n\n"
        f"Допустимые значения: 2, 3, 4, 5, н (не был), б (болел)"
    )

    await state.set_state(TeacherManualGrade.waiting_for_grade)


@router.message(TeacherManualGrade.waiting_for_grade)
async def manual_grade_input(message: Message, state: FSMContext):
    """
    Обработка ввода оценки и сохранение в БД
    """
    grade = message.text.strip()

    # Валидация оценки
    valid_grades = ['2', '3', '4', '5', 'н', 'Н', 'б', 'Б']
    if grade not in valid_grades:
        await message.answer(
            "❌ Неверная оценка.\n\n"
            "Допустимые значения: 2, 3, 4, 5, н (не был), б (болел)"
        )
        return

    # Нормализуем оценку
    grade = grade.lower()

    data = await state.get_data()
    teacher_username = data['teacher_username']
    subject = data['subject']
    class_name = data['class_name']
    student_name = data['student_name']
    date = data['date']

    # Сохраняем оценку в БД
    try:
        grade_data = {
            'student_name': student_name,
            'class': class_name,
            'subject': subject,
            'grade': grade,
            'date': date,
            'teacher_username': teacher_username
        }

        grade_repo.add_grade(
            student_name=student_name,
            class_name=class_name,
            subject=subject,
            grade=grade,
            grade_date=date,
            teacher_username=teacher_username
        )

        await message.answer(
            f"✅ Оценка успешно добавлена!\n\n"
            f"Ученик: {student_name}\n"
            f"Класс: {class_name}\n"
            f"Предмет: {subject}\n"
            f"Дата: {date}\n"
            f"Оценка: {grade}\n\n"
            f"Ученик получит уведомление о новой оценке."
        )

        # Отправляем уведомление ученику
        try:
            notification_service = NotificationService(message.bot)
            await notification_service.notify_students_new_grades([grade_data])
            print(f"[INFO] Sent grade notification for {student_name}")
        except Exception as notification_error:
            print(f"[ERROR] Failed to send grade notification: {notification_error}")

    except Exception as e:
        await message.answer(
            f"❌ Ошибка при сохранении оценки:\n\n"
            f"{str(e)}\n\n"
            f"Обратитесь к администратору."
        )

    finally:
        await state.clear()
