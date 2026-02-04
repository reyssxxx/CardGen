"""
Полный пайплайн OCR для обработки фотографий журналов
Объединяет предобработку изображений и распознавание
"""
import cv2
import numpy as np
from pathlib import Path
from typing import Dict, Optional, List
from datetime import datetime

from .image_processing import ImageProcessor
from .ocr_service import JournalOCR


class JournalOCRPipeline:
    """
    Полный пайплайн обработки фотографий журналов
    """

    def __init__(self, save_debug_images: bool = False):
        """
        Args:
            save_debug_images: Сохранять ли промежуточные изображения для отладки
        """
        self.image_processor = ImageProcessor()
        self.ocr = JournalOCR()
        self.save_debug_images = save_debug_images

    def process_journal_from_file(self, image_path: str,
                                  students_list: Optional[List[str]] = None,
                                  expected_class: Optional[str] = None) -> Dict:
        """
        Обработать фото журнала из файла

        Args:
            image_path: Путь к фотографии журнала
            students_list: Список валидных ФИО для сопоставления
            expected_class: Ожидаемый класс (для валидации)

        Returns:
            Словарь с результатами OCR:
            {
                'success': bool,
                'class': str,
                'dates': List[str],
                'students': List[Dict],
                'warnings': List[str],
                'debug_info': Dict
            }
        """
        warnings = []
        debug_info = {}

        try:
            print(f"[INFO] Starting journal processing: {image_path}")

            # Шаг 1: Предобработка изображения
            print("[INFO] Step 1/2: Image preprocessing...")
            preprocessed = self.image_processor.preprocess_for_ocr(
                image_path,
                save_debug=self.save_debug_images
            )

            if preprocessed is None:
                return {
                    'success': False,
                    'error': 'Failed to preprocess image',
                    'warnings': ['Could not load or process the image'],
                    'debug_info': debug_info
                }

            debug_info['preprocessed_shape'] = preprocessed.shape
            print(f"[INFO] Preprocessing complete. Image size: {preprocessed.shape}")

            # Шаг 2: OCR распознавание
            print("[INFO] Step 2/2: OCR recognition...")
            ocr_result = self.ocr.process_journal_photo(preprocessed, students_list)

            detected_class = ocr_result.get('class')
            dates = ocr_result.get('dates', [])
            students = ocr_result.get('students', [])

            debug_info['detected_class'] = detected_class
            debug_info['num_dates'] = len(dates)
            debug_info['num_students'] = len(students)

            # Валидация результатов
            if not detected_class:
                warnings.append('Class not detected from header')
            elif expected_class and detected_class != expected_class:
                warnings.append(
                    f'Detected class "{detected_class}" differs from expected "{expected_class}"'
                )

            if not dates:
                warnings.append('No dates detected from header row')

            if not students:
                warnings.append('No students detected')

            # Проверка качества распознавания имен
            if students_list and students:
                matched_count = 0
                for student_data in students:
                    if student_data['name'] in students_list:
                        matched_count += 1

                match_percentage = (matched_count / len(students)) * 100
                debug_info['name_match_percentage'] = match_percentage

                if match_percentage < 70:
                    warnings.append(
                        f'Only {match_percentage:.1f}% of names matched the student list. '
                        'Manual verification recommended.'
                    )

            # Проверка пустых оценок
            if students:
                total_grades = 0
                filled_grades = 0

                for student_data in students:
                    for grade in student_data.get('grades_row', []):
                        total_grades += 1
                        if grade is not None:
                            filled_grades += 1

                if total_grades > 0:
                    fill_percentage = (filled_grades / total_grades) * 100
                    debug_info['grade_fill_percentage'] = fill_percentage

                    if fill_percentage < 30:
                        warnings.append(
                            f'Only {fill_percentage:.1f}% of grade cells are filled. '
                            'Check image quality or OCR results.'
                        )

            print(f"[INFO] OCR complete. Class: {detected_class}, "
                  f"Dates: {len(dates)}, Students: {len(students)}")

            if warnings:
                print(f"[WARNING] {len(warnings)} warnings generated")
                for warning in warnings:
                    print(f"  - {warning}")

            return {
                'success': True,
                'class': detected_class,
                'dates': dates,
                'students': students,
                'warnings': warnings,
                'debug_info': debug_info
            }

        except Exception as e:
            print(f"[ERROR] Pipeline error: {e}")
            return {
                'success': False,
                'error': str(e),
                'warnings': warnings,
                'debug_info': debug_info
            }

    def validate_and_format_result(self, result: Dict, subject: str,
                                   teacher_username: str) -> Optional[Dict]:
        """
        Валидация и форматирование результата для сохранения в БД

        Args:
            result: Результат OCR пайплайна
            subject: Название предмета (вводится учителем)
            teacher_username: Username учителя

        Returns:
            Словарь с данными для bulk insert в БД или None при ошибке
            {
                'class': str,
                'subject': str,
                'teacher_username': str,
                'dates': List[str],
                'grades_data': List[Dict]  # для bulk insert
            }
        """
        if not result.get('success'):
            print(f"[ERROR] Cannot format failed OCR result: {result.get('error')}")
            return None

        detected_class = result.get('class')
        dates = result.get('dates', [])
        students = result.get('students', [])

        # Проверяем только критичное - должны быть студенты
        # Класс и даты могут быть пустыми, пользователь добавит вручную
        if not students:
            print("[ERROR] No students detected in OCR result")
            return None

        # Если класса нет, используем значение по умолчанию
        if not detected_class:
            detected_class = "Не определен"
            print("[WARNING] Class not detected, using default value")

        # Формируем данные для bulk insert
        grades_data = []

        for student_data in students:
            student_name = student_data['name']
            grades_row = student_data.get('grades_row', [])

            # Привязываем каждую оценку к дате
            for idx, grade in enumerate(grades_row):
                if idx >= len(dates):
                    break  # Больше оценок чем дат

                if grade is not None:  # Пропускаем пустые ячейки
                    grades_data.append({
                        'student_name': student_name,
                        'class': detected_class,
                        'subject': subject,
                        'grade': grade,
                        'date': dates[idx],
                        'teacher_username': teacher_username
                    })

        return {
            'class': detected_class,
            'subject': subject,
            'teacher_username': teacher_username,
            'dates': dates,
            'grades_data': grades_data
        }

    def process_and_prepare_for_db(self, image_path: str,
                                   subject: str,
                                   teacher_username: str,
                                   students_list: Optional[List[str]] = None,
                                   expected_class: Optional[str] = None) -> Dict:
        """
        Полный цикл: обработка изображения + подготовка данных для БД

        Returns:
            {
                'success': bool,
                'ocr_result': Dict,  # Сырые данные OCR
                'db_data': Dict,     # Данные готовые для БД
                'warnings': List[str]
            }
        """
        # OCR обработка
        ocr_result = self.process_journal_from_file(
            image_path,
            students_list,
            expected_class
        )

        if not ocr_result.get('success'):
            return {
                'success': False,
                'ocr_result': ocr_result,
                'db_data': None,
                'warnings': ocr_result.get('warnings', [])
            }

        # Форматирование для БД
        db_data = self.validate_and_format_result(
            ocr_result,
            subject,
            teacher_username
        )

        if db_data is None:
            return {
                'success': False,
                'ocr_result': ocr_result,
                'db_data': None,
                'warnings': ocr_result.get('warnings', []) + ['Failed to format data for database']
            }

        return {
            'success': True,
            'ocr_result': ocr_result,
            'db_data': db_data,
            'warnings': ocr_result.get('warnings', [])
        }


# Удобная функция для быстрого использования
def process_journal_photo(image_path: str,
                         subject: str,
                         teacher_username: str,
                         students_list: Optional[List[str]] = None,
                         expected_class: Optional[str] = None,
                         save_debug: bool = False) -> Dict:
    """
    Быстрая обработка фото журнала

    Args:
        image_path: Путь к фото
        subject: Предмет
        teacher_username: Username учителя
        students_list: Список валидных учеников (опционально)
        expected_class: Ожидаемый класс (опционально)
        save_debug: Сохранять отладочные изображения

    Returns:
        Результат обработки с данными для БД
    """
    pipeline = JournalOCRPipeline(save_debug_images=save_debug)
    return pipeline.process_and_prepare_for_db(
        image_path,
        subject,
        teacher_username,
        students_list,
        expected_class
    )
