"""
Форматирование данных для вывода
"""
from datetime import datetime
from typing import List, Dict
import html


def format_date(date_string: str, input_format: str = '%Y-%m-%d',
                output_format: str = '%d.%m.%Y') -> str:
    """
    Форматирование даты
    По умолчанию: '2026-01-15' -> '15.01.2026'
    """
    try:
        date_obj = datetime.strptime(date_string, input_format)
        return date_obj.strftime(output_format)
    except (ValueError, TypeError):
        return date_string


def format_grades_list(grades: List[str]) -> str:
    """
    Форматирование списка оценок
    ['5', '4', '5', None, '3'] -> '5, 4, 5, -, 3'
    """
    formatted = []
    for grade in grades:
        if grade is None or grade == '':
            formatted.append('-')
        else:
            formatted.append(str(grade))

    return ', '.join(formatted)


def calculate_average(grades: List[str]) -> float:
    """
    Расчет среднего балла из списка оценок
    Учитываются только цифровые оценки (2-5)
    """
    numeric_grades = []
    for grade in grades:
        if grade and grade.isdigit() and grade in ['2', '3', '4', '5']:
            numeric_grades.append(int(grade))

    if not numeric_grades:
        return 0.0

    return round(sum(numeric_grades) / len(numeric_grades), 2)


def format_grade_with_average(grades: List[str]) -> str:
    """
    Форматирование оценок со средним баллом
    ['5', '4', '5', '5'] -> '5, 4, 5, 5 (средний: 4.75)'
    """
    grades_str = format_grades_list(grades)
    average = calculate_average(grades)

    if average > 0:
        return f"{grades_str} (средний: {average})"
    else:
        return grades_str


def format_student_grades_report(student_name: str, grades_by_subject: Dict) -> str:
    """
    Форматирование отчета об оценках ученика
    """
    report_lines = [f"📊 Оценки для {student_name}:\n"]

    if not grades_by_subject:
        return f"📊 Оценки для {student_name}:\n\nОценок пока нет."

    for subject, grades in grades_by_subject.items():
        grade_str = format_grade_with_average(grades)
        report_lines.append(f"{subject}: {grade_str}")

    return '\n'.join(report_lines)


def format_statistics(stats: Dict) -> str:
    """
    Форматирование статистики оценок
    """
    lines = ["📈 Статистика оценок:\n"]

    if 'grade_counts' in stats:
        counts = stats['grade_counts']
        if '5' in counts:
            lines.append(f"Пятерки: {counts['5']}")
        if '4' in counts:
            lines.append(f"Четверки: {counts['4']}")
        if '3' in counts:
            lines.append(f"Тройки: {counts['3']}")
        if '2' in counts:
            lines.append(f"Двойки: {counts['2']}")

    if 'average_grade' in stats and stats['average_grade']:
        lines.append(f"\n💯 Средний балл: {stats['average_grade']}")

    if 'total_grades' in stats:
        lines.append(f"\n📝 Всего оценок: {stats['total_grades']}")

    return '\n'.join(lines)


def escape_html(text: str) -> str:
    """
    Экранирование HTML для Telegram
    """
    return html.escape(str(text))


def format_class_statistics(class_name: str, stats: Dict) -> str:
    """
    Форматирование статистики по классу
    """
    lines = [f"📊 Статистика класса {class_name}:\n"]

    if stats.get('average_grade'):
        lines.append(f"Средний балл класса: {stats['average_grade']}")

    if 'grade_counts' in stats:
        counts = stats['grade_counts']
        lines.append("\nРаспределение оценок:")
        for grade in ['5', '4', '3', '2']:
            if grade in counts:
                lines.append(f"  {grade}: {counts[grade]} шт.")

    return '\n'.join(lines)


def format_teacher_reminder(teacher_name: str, subject: str) -> str:
    """
    Форматирование напоминания учителю
    """
    return f"""📸 Напоминание для {teacher_name}

Пожалуйста, загрузите фотографию журнала по предмету "{subject}".

Используйте команду /photo для загрузки."""


def format_new_grades_notification(student_name: str, grades_info: List[Dict]) -> str:
    """
    Форматирование уведомления о новых оценках
    grades_info: список словарей с ключами subject, date, grade
    """
    lines = [f"📚 {student_name}, у тебя новые оценки!\n"]

    # Группируем по предметам
    by_subject = {}
    for info in grades_info:
        subject = info['subject']
        if subject not in by_subject:
            by_subject[subject] = []
        by_subject[subject].append((info['date'], info['grade']))

    for subject, grades in by_subject.items():
        lines.append(f"\n{subject}:")
        for date, grade in grades:
            formatted_date = format_date(date, '%Y-%m-%d', '%d.%m')
            lines.append(f"  • {formatted_date} - {grade}")

    lines.append("\n/getcard - посмотреть полный табель")

    return '\n'.join(lines)


def format_journal_status(uploads_data: List[Dict]) -> str:
    """
    Форматирование статуса журнала (кто загрузил, кто нет)
    """
    if not uploads_data:
        return "📋 За последнюю неделю загрузок не было."

    lines = ["📋 Статус журнала за неделю:\n"]

    for upload in uploads_data:
        teacher = upload['teacher_username']
        subject = upload['subject']
        class_name = upload['class']
        status_icon = "✅" if upload['status'] == 'processed' else "⏳"

        date = format_date(upload['upload_date'], '%Y-%m-%d %H:%M:%S', '%d.%m %H:%M')

        lines.append(f"{status_icon} {teacher} | {subject} | {class_name} | {date}")

    return '\n'.join(lines)


def truncate_text(text: str, max_length: int = 4000) -> str:
    """
    Обрезка текста до максимальной длины (для Telegram)
    """
    if len(text) <= max_length:
        return text

    return text[:max_length-3] + "..."
