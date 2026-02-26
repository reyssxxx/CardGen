"""
Сервис импорта оценок из Excel и генерации шаблонов.
"""
import re
from datetime import datetime
from typing import Optional
import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
import io


VALID_GRADES = {'2', '3', '4', '5', 'н', 'б'}


def parse_grades_excel(file_path: str, class_name: str, valid_students: list) -> dict:
    """
    Парсит Excel-файл с оценками.

    Формат файла:
      Строка 1 (заголовки): Ученик | Предмет | 01.09.2024 | 15.09.2024 | ...
      Строки 2+:            Иванов Иван | Математика | 5 | 4 3 | ...

    Несколько оценок в ячейке — разделяются пробелами.
    Пустая ячейка = нет оценок за период.

    Returns:
        {
            'grades': [{'student_name', 'class', 'subject', 'grade', 'date'}, ...],
            'skipped': ['Имя которое не найдено', ...],
            'dates': [datetime, ...],
            'count': int,
        }
    """
    valid_lower = {s.lower(): s for s in valid_students}

    wb = openpyxl.load_workbook(file_path)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Файл пустой")

    header = rows[0]
    if len(header) < 3:
        raise ValueError("Неверный формат: нужно минимум 3 столбца (Ученик, Предмет, Дата...)")

    # Парсим даты из заголовков (с 3-го столбца)
    dates = []
    for cell in header[2:]:
        if cell is None:
            break
        date = _parse_date(str(cell).strip())
        if date:
            dates.append(date)

    if not dates:
        raise ValueError("Не найдено ни одной даты в заголовке (формат: ДД.ММ.ГГГГ)")

    grades_list = []
    skipped = []

    for row in rows[1:]:
        if not row or row[0] is None:
            continue

        student_raw = str(row[0]).strip()
        subject = str(row[1]).strip() if row[1] else None

        if not student_raw or not subject:
            continue

        # Fuzzy-match имя
        matched_name = _match_name(student_raw, valid_lower)
        if not matched_name:
            if student_raw not in skipped:
                skipped.append(student_raw)
            continue

        # Парсим оценки по датам
        for i, date in enumerate(dates):
            col_idx = i + 2
            cell_value = row[col_idx] if col_idx < len(row) else None
            if cell_value is None or str(cell_value).strip() == '':
                continue

            cell_str = str(cell_value).strip()
            grade_tokens = cell_str.split()

            for token in grade_tokens:
                token = token.lower().strip()
                if token in VALID_GRADES:
                    grades_list.append({
                        'student_name': matched_name,
                        'class': class_name,
                        'subject': subject,
                        'grade': token,
                        'date': date.strftime('%d.%m.%Y'),
                    })

    return {
        'grades': grades_list,
        'skipped': skipped,
        'dates': dates,
        'count': len(grades_list),
    }


def generate_template_excel(class_name: str, students: list, subjects: list) -> bytes:
    """
    Генерирует Excel-шаблон для заполнения оценок.

    Returns:
        bytes: содержимое .xlsx файла
    """
    wb = Workbook()
    ws = wb.active
    ws.title = class_name

    # Стили
    header_fill = PatternFill(start_color="1E40AF", end_color="1E40AF", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    center = Alignment(horizontal="center", vertical="center")
    thin = Side(style='thin', color='93C5FD')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # Заголовочная строка
    ws.cell(1, 1, "Ученик").font = header_font
    ws.cell(1, 1).fill = header_fill
    ws.cell(1, 1).alignment = center
    ws.cell(1, 1).border = border
    ws.column_dimensions['A'].width = 30

    ws.cell(1, 2, "Предмет").font = header_font
    ws.cell(1, 2).fill = header_fill
    ws.cell(1, 2).alignment = center
    ws.cell(1, 2).border = border
    ws.column_dimensions['B'].width = 20

    # Пример дат (2 в месяц с 1 сентября текущего учебного года)
    now = datetime.now()
    year = now.year if now.month >= 9 else now.year - 1
    from datetime import timedelta
    period = datetime(year, 9, 1)
    example_dates = []
    while period <= now:
        example_dates.append(period)
        period += timedelta(weeks=2)

    col_letters = []
    for i, date in enumerate(example_dates):
        col = i + 3
        header_cell = ws.cell(1, col, date.strftime('%d.%m.%Y'))
        header_cell.font = header_font
        header_cell.fill = header_fill
        header_cell.alignment = center
        header_cell.border = border
        col_letter = ws.cell(1, col).column_letter
        ws.column_dimensions[col_letter].width = 12
        col_letters.append(col_letter)

    # Данные: ученик × предмет
    row_idx = 2
    alt_fill = PatternFill(start_color="EFF6FF", end_color="EFF6FF", fill_type="solid")
    for student in students:
        for subject in subjects:
            ws.cell(row_idx, 1, student).border = border
            ws.cell(row_idx, 1).alignment = Alignment(vertical="center")
            ws.cell(row_idx, 2, subject).border = border
            ws.cell(row_idx, 2).alignment = Alignment(vertical="center")
            if row_idx % 2 == 0:
                ws.cell(row_idx, 1).fill = alt_fill
                ws.cell(row_idx, 2).fill = alt_fill
            for i in range(len(example_dates)):
                cell = ws.cell(row_idx, i + 3)
                cell.border = border
                cell.alignment = center
            row_idx += 1

    # Инструкция в конце
    ws.cell(row_idx + 1, 1, "Допустимые оценки: 2 3 4 5 н б (можно несколько в ячейке через пробел)")

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def _parse_date(value: str) -> Optional[datetime]:
    """Попытаться распарсить дату из строки."""
    for fmt in ('%d.%m.%Y', '%d.%m.%y', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _match_name(raw: str, valid_lower: dict) -> Optional[str]:
    """Точное или case-insensitive совпадение имени."""
    key = raw.lower().strip()
    return valid_lower.get(key)
