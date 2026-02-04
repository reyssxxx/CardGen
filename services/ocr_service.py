"""
OCR сервис для распознавания оценок с фотографий журналов
Использует EasyOCR для распознавания текста
"""
import re
import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# EasyOCR будет импортирован при первом использовании (ленивая загрузка)
_easyocr_reader = None


def get_ocr_reader():
    """Ленивая инициализация EasyOCR reader"""
    global _easyocr_reader
    if _easyocr_reader is None:
        try:
            import easyocr
            print("[INFO] Initializing EasyOCR reader (this may take a moment)...")
            _easyocr_reader = easyocr.Reader(['ru', 'en'], gpu=False)
            print("[INFO] EasyOCR reader initialized successfully")
        except ImportError:
            raise ImportError("EasyOCR not installed. Run: pip install easyocr")
    return _easyocr_reader


class JournalOCR:
    def __init__(self):
        self.reader = None  # Будет инициализирован при первом использовании

    def _ensure_reader(self):
        """Убедиться что reader инициализирован"""
        if self.reader is None:
            self.reader = get_ocr_reader()

    def extract_text_from_image(self, image: np.ndarray) -> List[Tuple]:
        """
        Извлечь весь текст из изображения
        Возвращает: список (bbox, text, confidence)

        ОПТИМИЗИРОВАНО для рукописного текста
        """
        self._ensure_reader()

        # Параметры оптимизированные для рукописного текста
        results = self.reader.readtext(
            image,
            detail=1,              # Получать bbox и confidence
            paragraph=False,       # Не группировать в параграфы
            min_size=10,          # Минимальный размер текста
            text_threshold=0.6,   # СНИЖЕН порог для рукописи (было 0.7)
            low_text=0.3,         # Порог для детекции текста
            link_threshold=0.3,   # Порог для связывания символов
            canvas_size=2560,     # Размер canvas для обработки
            mag_ratio=1.5         # Увеличение для лучшей детекции
        )
        return results

    def extract_class_from_header(self, image: np.ndarray) -> Optional[str]:
        """
        Распознать класс из заголовка
        Ищет паттерн "11-т КЛАССА" или "10Г КЛАССА"
        """
        # Берем только верхнюю часть изображения (заголовок)
        height = image.shape[0]
        header = image[0:int(height * 0.15), :]

        self._ensure_reader()
        results = self.reader.readtext(header)

        # Ищем паттерн класса
        class_pattern = r'(\d{1,2})[- ]?([А-ЯЁ]+)'

        for (bbox, text, conf) in results:
            # Ищем "КЛАССА" или "класс"
            if 'класс' in text.lower():
                # Ищем класс в этой строке или рядом
                match = re.search(class_pattern, text, re.IGNORECASE)
                if match:
                    grade = match.group(1)
                    letter = match.group(2).upper()
                    return f"{grade}{letter}"

        # Если не нашли вместе с "КЛАССА", ищем отдельно
        all_text = ' '.join([text for (_, text, _) in results])
        match = re.search(class_pattern, all_text)
        if match:
            grade = match.group(1)
            letter = match.group(2).upper()
            return f"{grade}{letter}"

        return None

    def extract_dates_from_header(self, image: np.ndarray) -> List[str]:
        """
        Распознать даты из строки заголовка таблицы
        Формат: ДД.ММ (например: 01.09, 03.09, 11.01)

        Стратегия:
        1. Ищем строку с датами (обычно это 2-3 строка таблицы)
        2. Распознаем все даты в формате ДД.ММ
        3. Сортируем слева направо
        """
        # Берем верхнюю треть изображения (где обычно находятся даты)
        height = image.shape[0]
        dates_region = image[int(height * 0.1):int(height * 0.25), :]

        self._ensure_reader()
        results = self.reader.readtext(dates_region)

        dates = []
        date_pattern = r'(\d{1,2})[./](\d{1,2})'

        for (bbox, text, conf) in results:
            # Ищем даты в тексте
            matches = re.findall(date_pattern, text)
            for match in matches:
                day, month = match
                # Нормализуем формат
                day = day.zfill(2)
                month = month.zfill(2)
                date_str = f"{day}.{month}"

                # Добавляем год (текущий)
                current_year = datetime.now().year
                full_date = f"{day}.{month}.{current_year}"

                # Сохраняем вместе с координатой X для сортировки
                bbox_x = bbox[0][0]  # X координата левого верхнего угла
                dates.append((bbox_x, full_date))

        # Сортируем слева направо
        dates.sort(key=lambda x: x[0])

        # Возвращаем только даты
        return [date for (_, date) in dates]

    def extract_student_names(self, image: np.ndarray) -> List[str]:
        """
        Распознать ФИО учеников из второго столбца
        """
        # Берем левую часть изображения (где обычно ФИО)
        width = image.shape[1]
        names_region = image[:, 0:int(width * 0.25)]

        self._ensure_reader()
        results = self.reader.readtext(names_region)

        names = []

        # Фильтруем: оставляем только строки с буквами (ФИО)
        for (bbox, text, conf) in results:
            # УЛУЧШЕНИЕ 1: Фильтр по confidence score
            if conf < 0.4:  # Отбрасываем ненадёжное распознавание
                print(f"[DEBUG] Skipping low confidence text: '{text}' (conf={conf:.2f})")
                continue

            # Пропускаем заголовки и номера
            if re.match(r'^\d+\.?$', text.strip()):
                continue
            if len(text.strip()) < 3:
                continue
            if 'класс' in text.lower() or 'фио' in text.lower() or 'ф.и' in text.lower():
                continue

            # УЛУЧШЕНИЕ 2: Нормализация русского текста
            normalized_text = self._normalize_russian_name(text.strip())
            if not normalized_text:  # Пропускаем если после нормализации пусто
                continue

            # Это вероятно ФИО
            # Сохраняем вместе с Y координатой для сортировки
            bbox_y = bbox[0][1]  # Y координата
            names.append((bbox_y, normalized_text, conf))

        # Сортируем сверху вниз
        names.sort(key=lambda x: x[0])

        # Возвращаем только имена
        return [name for (_, name, _) in names]

    def _normalize_russian_name(self, text: str) -> str:
        """
        Нормализация русских имён для исправления типичных ошибок OCR
        """
        # 1. Унификация пробелов
        text = ' '.join(text.split())

        # 2. Исправление типичных ошибок OCR с кириллицей
        replacements = {
            '0': 'О',   # 0 вместо О
            'o': 'о',   # Латинская o вместо кириллической о
            'O': 'О',   # Латинская O вместо кириллической О
            'a': 'а',   # Латинская a вместо кириллической а
            'A': 'А',   # Латинская A вместо кириллической А
            'e': 'е',   # Латинская e вместо кириллической е
            'E': 'Е',   # Латинская E вместо кириллической Е
            'c': 'с',   # Латинская c вместо кириллической с
            'C': 'С',   # Латинская C вместо кириллической С
            'p': 'р',   # Латинская p вместо кириллической р
            'P': 'Р',   # Латинская P вместо кириллической Р
            'x': 'х',   # Латинская x вместо кириллической х
            'X': 'Х',   # Латинская X вместо кириллической Х
            'B': 'В',   # Латинская B вместо кириллической В
            'H': 'Н',   # Латинская H вместо кириллической Н
            'K': 'К',   # Латинская K вместо кириллической К
            'M': 'М',   # Латинская M вместо кириллической М
            'T': 'Т',   # Латинская T вместо кириллической Т
        }

        for wrong, correct in replacements.items():
            text = text.replace(wrong, correct)

        # 3. Правильное капитализирование для ФИО (Каждое Слово С Большой Буквы)
        text = ' '.join(word.capitalize() for word in text.split())

        # 4. Удаление не-кириллических символов (кроме пробелов и дефисов)
        text = re.sub(r'[^а-яА-ЯёЁ\s\-]', '', text)

        return text.strip()

    def extract_grades_grid(self, image: np.ndarray,
                           num_students: int,
                           num_columns: int) -> List[List[Optional[str]]]:
        """
        Извлечь оценки из таблицы (2D массив)

        Стратегия:
        1. Детектируем границы ячеек таблицы
        2. Для каждой ячейки запускаем OCR
        3. Валидируем что это оценка (2-5, н/н, н, б)

        Возвращает: grades[student_index][column_index]
        """
        # Это сложная задача, требует детекции сетки таблицы
        # Упрощенная версия: разбиваем изображение на сетку

        height, width = image.shape[:2]

        # Примерное расположение:
        # - Первые 20% ширины - номера и ФИО
        # - Остальные 80% - оценки
        # - Первые 15% высоты - заголовок
        # - Остальное - строки с учениками

        grades_start_x = int(width * 0.25)
        grades_start_y = int(height * 0.15)

        grades_region = image[grades_start_y:, grades_start_x:]

        # Делим регион на сетку
        cell_height = (height - grades_start_y) // (num_students + 1)
        cell_width = (width - grades_start_x) // (num_columns + 1)

        grades = []

        self._ensure_reader()

        for student_idx in range(num_students):
            student_grades = []

            for col_idx in range(num_columns):
                # Координаты ячейки
                y1 = student_idx * cell_height
                y2 = (student_idx + 1) * cell_height
                x1 = col_idx * cell_width
                x2 = (col_idx + 1) * cell_width

                # Извлекаем ячейку
                cell = grades_region[y1:y2, x1:x2]

                # OCR ячейки
                try:
                    cell_results = self.reader.readtext(cell)

                    grade = None
                    for (_, text, conf) in cell_results:
                        text = text.strip()
                        # Валидация оценки
                        if self._is_valid_grade(text):
                            grade = self._normalize_grade(text)
                            break

                    student_grades.append(grade)

                except:
                    student_grades.append(None)

            grades.append(student_grades)

        return grades

    def _is_valid_grade(self, text: str) -> bool:
        """Проверка что текст - это оценка"""
        text = text.lower().strip()

        valid_grades = {'2', '3', '4', '5', 'н/н', 'н', 'б', 'нн', 'н.', 'б.'}

        return text in valid_grades

    def _normalize_grade(self, text: str) -> str:
        """Нормализация оценки к стандартному формату"""
        text = text.lower().strip()

        # Маппинг вариаций
        if text in ['нн', 'н.н', 'н.']:
            return 'н/н'
        if text in ['б', 'б.']:
            return 'б'
        if text in ['н']:
            return 'н'

        return text

    def process_journal_photo(self, image: np.ndarray,
                             students_list: Optional[List[str]] = None) -> Dict:
        """
        Главная функция обработки фото журнала

        Возвращает словарь с результатами:
        {
            'class': '11Т',
            'dates': ['01.09.2026', '03.09.2026', ...],
            'students': [
                {'name': 'Иванов Иван', 'grades_row': ['5', '4', None, '5']},
                ...
            ]
        }
        """
        print("[INFO] Starting OCR processing...")

        # 1. Извлекаем класс
        print("[INFO] Extracting class...")
        detected_class = self.extract_class_from_header(image)
        print(f"[INFO] Detected class: {detected_class}")

        # 2. Извлекаем даты
        print("[INFO] Extracting dates...")
        dates = self.extract_dates_from_header(image)
        print(f"[INFO] Detected {len(dates)} dates: {dates[:5]}...")

        # 3. Извлекаем ФИО
        print("[INFO] Extracting student names...")
        detected_names = self.extract_student_names(image)
        print(f"[INFO] Detected {len(detected_names)} students")

        # Если передан список учеников для валидации
        if students_list:
            # Сопоставляем распознанные имена со списком
            validated_names = self._match_names(detected_names, students_list)
        else:
            validated_names = detected_names

        # 4. Извлекаем оценки
        print("[INFO] Extracting grades...")
        num_students = len(validated_names)
        num_columns = len(dates) if dates else 5  # По умолчанию 5 столбцов

        # Упрощенная версия: не используем сложную детекцию сетки
        # Вместо этого используем OCR всего изображения и сопоставляем координаты
        grades_grid = self._extract_grades_simple(image, num_students, num_columns)

        # 5. Формируем результат
        students = []
        for idx, name in enumerate(validated_names):
            if idx < len(grades_grid):
                student_data = {
                    'name': name,
                    'grades_row': grades_grid[idx]
                }
                students.append(student_data)

        result = {
            'class': detected_class,
            'dates': dates,
            'students': students
        }

        print(f"[INFO] OCR processing completed. Found {len(students)} students with {len(dates)} dates")

        return result

    def _extract_grades_simple(self, image: np.ndarray,
                               num_students: int, num_columns: int) -> List[List[Optional[str]]]:
        """
        Упрощенная версия извлечения оценок
        Использует OCR всего изображения и группирует по позиции
        """
        self._ensure_reader()
        all_results = self.reader.readtext(image)

        # Фильтруем только оценки
        grades_results = []
        for (bbox, text, conf) in all_results:
            if self._is_valid_grade(text):
                # bbox: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
                x = bbox[0][0]
                y = bbox[0][1]
                grade = self._normalize_grade(text)
                grades_results.append((x, y, grade))

        # Группируем по строкам (Y координата)
        # Сортируем по Y
        grades_results.sort(key=lambda item: item[1])

        # Группируем в строки
        rows = []
        current_row = []
        last_y = 0
        y_threshold = 30  # Пикселей разницы по Y для одной строки

        for (x, y, grade) in grades_results:
            if last_y == 0 or abs(y - last_y) < y_threshold:
                current_row.append((x, grade))
                last_y = y
            else:
                if current_row:
                    # Сортируем по X и добавляем строку
                    current_row.sort(key=lambda item: item[0])
                    rows.append([g for (_, g) in current_row])
                current_row = [(x, grade)]
                last_y = y

        # Добавляем последнюю строку
        if current_row:
            current_row.sort(key=lambda item: item[0])
            rows.append([g for (_, g) in current_row])

        # Дополняем до нужного размера
        result = []
        for i in range(num_students):
            if i < len(rows):
                row = rows[i]
                # Дополняем None до num_columns
                while len(row) < num_columns:
                    row.append(None)
                result.append(row[:num_columns])
            else:
                result.append([None] * num_columns)

        return result

    def _match_names(self, detected_names: List[str],
                    valid_names: List[str]) -> List[str]:
        """
        Сопоставление распознанных имен с валидным списком
        Использует нечеткое сравнение

        УЛУЧШЕНИЕ 3: Снижен порог с 0.6 до 0.5 для лучшего сопоставления
        """
        from difflib import get_close_matches

        matched = []
        for detected in detected_names:
            # Точное совпадение (быстрый путь)
            if detected in valid_names:
                matched.append(detected)
                print(f"[DEBUG] Exact match: '{detected}'")
                continue

            # Нечеткий поиск с пониженным порогом
            matches = get_close_matches(
                detected.lower(),
                [n.lower() for n in valid_names],
                n=1,
                cutoff=0.5  # СНИЖЕНО с 0.6 до 0.5
            )

            if matches:
                # Находим оригинальное имя
                for valid_name in valid_names:
                    if valid_name.lower() == matches[0]:
                        matched.append(valid_name)
                        print(f"[DEBUG] Fuzzy match: '{detected}' -> '{valid_name}'")
                        break
            else:
                # Оставляем как есть если не нашли совпадение
                matched.append(detected)
                print(f"[DEBUG] No match found for: '{detected}', keeping as-is")

        return matched


# Удобная функция для быстрого использования
def extract_grades_from_journal(image: np.ndarray,
                                students_list: Optional[List[str]] = None) -> Dict:
    """
    Извлечь оценки из фото журнала

    Args:
        image: Обработанное изображение (после image_processing)
        students_list: Список валидных ФИО для сопоставления

    Returns:
        Словарь с классом, датами и оценками учеников
    """
    ocr = JournalOCR()
    return ocr.process_journal_photo(image, students_list)
