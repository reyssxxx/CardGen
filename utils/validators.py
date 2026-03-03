"""
Валидаторы для проверки данных
"""
import re
from datetime import datetime
from typing import Optional


def validate_full_name(name: str) -> bool:
    """
    Валидация ФИО
    Должно быть минимум 2 слова (Фамилия Имя или Фамилия Имя Отчество)
    """
    if not name or not isinstance(name, str):
        return False

    # Убираем лишние пробелы
    name = name.strip()

    # Минимум 2 слова
    words = name.split()
    if len(words) < 2:
        return False

    # Каждое слово должно начинаться с заглавной буквы и содержать только буквы
    for word in words:
        if not word or not word[0].isupper():
            return False
        # Проверяем что содержит только буквы (русские или английские) и дефис
        if not re.match(r'^[А-ЯЁа-яёA-Za-z\-]+$', word):
            return False

    return True


def validate_grade(grade: str) -> bool:
    """
    Валидация оценки
    Допустимые значения: 2, 3, 4, 5, н/н, н, б
    """
    if not grade or not isinstance(grade, str):
        return False

    valid_grades = {'2', '3', '4', '5', 'н/н', 'н', 'б'}
    return grade.lower() in valid_grades


def validate_date(date_string: str, format: str = '%d.%m.%Y') -> bool:
    """
    Валидация даты
    По умолчанию формат: ДД.ММ.ГГГГ
    """
    if not date_string or not isinstance(date_string, str):
        return False

    try:
        datetime.strptime(date_string, format)
        return True
    except ValueError:
        # Попробуем альтернативный формат ДД.ММ
        try:
            datetime.strptime(date_string, '%d.%m')
            return True
        except ValueError:
            return False


def validate_time(time_string: str) -> bool:
    """
    Валидация времени в формате ЧЧ:ММ
    """
    if not time_string or not isinstance(time_string, str):
        return False
    try:
        datetime.strptime(time_string.strip(), '%H:%M')
        return True
    except ValueError:
        return False


def validate_username(username: str) -> bool:
    """
    Валидация Telegram username
    Должен начинаться с буквы, содержать только буквы, цифры и подчеркивания
    Длина: 5-32 символа
    """
    if not username or not isinstance(username, str):
        return False

    # Убираем @ если есть
    username = username.lstrip('@')

    # Проверка формата
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$', username):
        return False

    return True


def validate_class_name(class_name: str) -> bool:
    """
    Валидация названия класса
    Формат: 10Т, 11Г, 10СЭ и т.д.
    """
    if not class_name or not isinstance(class_name, str):
        return False

    # Должно начинаться с цифры (9-11), затем буквы
    if not re.match(r'^(9|10|11)[А-ЯЁ]+$', class_name):
        return False

    return True


def validate_subject(subject: str, valid_subjects: list) -> bool:
    """
    Валидация предмета (проверка что предмет есть в списке)
    """
    if not subject or not isinstance(subject, str):
        return False

    return subject in valid_subjects


def normalize_full_name(name: str) -> str:
    """
    Нормализация ФИО - приведение к стандартному виду
    "иванов иван" -> "Иванов Иван"
    """
    if not name:
        return ""

    # Убираем лишние пробелы и приводим к нижнему регистру
    name = ' '.join(name.strip().split())

    # Каждое слово с заглавной буквы
    words = name.split()
    normalized = ' '.join(word.capitalize() for word in words)

    return normalized


def parse_date_with_year(date_string: str, default_year: Optional[int] = None) -> str:
    """
    Парсинг даты и добавление года если не указан
    "01.09" -> "01.09.2026" (текущий или указанный год)
    """
    if not date_string:
        return ""

    # Если год не указан, берем текущий или default_year
    if default_year is None:
        default_year = datetime.now().year

    # Пробуем распарсить с годом
    try:
        datetime.strptime(date_string, '%d.%m.%Y')
        return date_string  # Год уже есть
    except ValueError:
        pass

    # Пробуем без года
    try:
        date_obj = datetime.strptime(date_string, '%d.%m')
        return f"{date_string}.{default_year}"
    except ValueError:
        return ""


def sanitize_filename(filename: str) -> str:
    """
    Очистка имени файла от недопустимых символов
    """
    # Убираем недопустимые символы для имени файла
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)

    # Убираем лишние пробелы
    filename = '_'.join(filename.split())

    return filename
