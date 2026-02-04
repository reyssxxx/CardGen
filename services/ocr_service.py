"""
OCR сервис для распознавания оценок с фотографий журналов
Использует EasyOCR для распознавания текста
Опционально использует Tesseract для печатного текста (имена)
Использует GradeCellDetector и GradeOCREngine для точного распознавания оценок из ячеек
"""
import re
import cv2
import numpy as np
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# EasyOCR будет импортирован при первом использовании (ленивая загрузка)
_easyocr_reader = None
_tesseract_extractor = None
_grade_cell_detector = None
_grade_ocr_engine = None
_document_scanner = None


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
    def __init__(self, use_tesseract_for_names: bool = True):
        """
        Args:
            use_tesseract_for_names: Использовать Tesseract для печатных имен (рекомендуется)
        """
        self.reader = None  # Будет инициализирован при первом использовании
        self.use_tesseract_for_names = use_tesseract_for_names
        self.tesseract = None
        self.original_image = None  # Оригинальное изображение для Tesseract

    def _ensure_reader(self):
        """Убедиться что reader инициализирован"""
        if self.reader is None:
            self.reader = get_ocr_reader()

    def _get_tesseract(self):
        """Получить Tesseract extractor (ленивая инициализация)"""
        global _tesseract_extractor
        if _tesseract_extractor is None:
            try:
                from .tesseract_ocr import TesseractNameExtractor
                _tesseract_extractor = TesseractNameExtractor()
                if not _tesseract_extractor.is_available():
                    print("[INFO] Tesseract not available, will use EasyOCR only")
                    _tesseract_extractor = None
            except Exception as e:
                print(f"[WARNING] Could not initialize Tesseract: {e}")
                _tesseract_extractor = None
        return _tesseract_extractor

    def _get_cell_detector(self):
        """Получить GradeCellDetector (ленивая инициализация)"""
        global _grade_cell_detector
        if _grade_cell_detector is None:
            try:
                try:
                    from .grade_cell_detector import GradeCellDetector
                except ImportError:
                    from grade_cell_detector import GradeCellDetector
                _grade_cell_detector = GradeCellDetector(debug=False)
                print("[INFO] GradeCellDetector initialized")
            except Exception as e:
                print(f"[WARNING] Could not initialize GradeCellDetector: {e}")
                _grade_cell_detector = None
        return _grade_cell_detector

    def _get_grade_ocr_engine(self):
        """Получить GradeOCREngine (ленивая инициализация)"""
        global _grade_ocr_engine
        if _grade_ocr_engine is None:
            try:
                try:
                    from .grade_ocr import GradeOCREngine
                except ImportError:
                    from grade_ocr import GradeOCREngine
                _grade_ocr_engine = GradeOCREngine(debug=False)
                print("[INFO] GradeOCREngine initialized")
            except Exception as e:
                print(f"[WARNING] Could not initialize GradeOCREngine: {e}")
                _grade_ocr_engine = None
        return _grade_ocr_engine

    def _get_document_scanner(self):
        """Получить DocumentScanner (ленивая инициализация)"""
        global _document_scanner
        if _document_scanner is None:
            try:
                try:
                    from .document_scanner import DocumentScanner
                except ImportError:
                    from document_scanner import DocumentScanner
                _document_scanner = DocumentScanner()
                print("[INFO] DocumentScanner initialized")
            except Exception as e:
                print(f"[WARNING] Could not initialize DocumentScanner: {e}")
                _document_scanner = None
        return _document_scanner

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
        Сначала пробует Tesseract (лучше для печатного текста),
        затем fallback на EasyOCR
        """
        # ПОПЫТКА 1: Tesseract для печатного текста
        if self.use_tesseract_for_names:
            tesseract = self._get_tesseract()
            if tesseract and tesseract.is_available():
                print("[INFO] Trying Tesseract for name extraction...")
                try:
                    # Используем оригинальное изображение если доступно
                    test_image = self.original_image if self.original_image is not None else image
                    names = tesseract.extract_names(test_image, names_region_width=0.30)
                    if names and len(names) > 0:
                        print(f"[INFO] Tesseract successfully extracted {len(names)} names")
                        return names
                    else:
                        print("[INFO] Tesseract found no names, falling back to EasyOCR")
                except Exception as e:
                    print(f"[WARNING] Tesseract failed: {e}, falling back to EasyOCR")

        # ПОПЫТКА 2: EasyOCR (fallback или основной метод)
        print("[INFO] Using EasyOCR for name extraction...")

        # Берем левую часть изображения (где обычно ФИО)
        width = image.shape[1]
        names_region = image[:, 0:int(width * 0.25)]

        # ДОПОЛНИТЕЛЬНАЯ предобработка для области с именами
        # Увеличиваем контраст и резкость
        import cv2

        # Увеличиваем размер изображения для лучшего распознавания
        height, width_orig = names_region.shape[:2]
        scale_factor = 2.0
        names_region = cv2.resize(names_region, None, fx=scale_factor, fy=scale_factor,
                                   interpolation=cv2.INTER_CUBIC)

        # Улучшаем контраст с CLAHE
        if len(names_region.shape) == 2:  # Grayscale
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            names_region = clahe.apply(names_region)
        else:  # Color
            lab = cv2.cvtColor(names_region, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            names_region = cv2.merge([l, a, b])
            names_region = cv2.cvtColor(names_region, cv2.COLOR_LAB2BGR)

        # Увеличиваем резкость
        kernel = np.array([[-1, -1, -1],
                          [-1,  9, -1],
                          [-1, -1, -1]])
        names_region = cv2.filter2D(names_region, -1, kernel)

        self._ensure_reader()

        # УЛУЧШЕННЫЕ параметры для ПЕЧАТНОГО текста (имена в журналах обычно печатные)
        results = self.reader.readtext(
            names_region,
            detail=1,
            paragraph=False,
            min_size=20,           # УВЕЛИЧЕН для печатного текста с учетом scale
            text_threshold=0.7,    # ПОВЫШЕН для печатного текста
            low_text=0.4,          # Порог детекции
            link_threshold=0.4,    # Порог связывания
            canvas_size=3840,      # УВЕЛИЧЕН размер canvas
            mag_ratio=1.5,         # Mag ratio (не нужно много т.к. уже увеличили)
            width_ths=0.7,         # Порог ширины для группировки
            ycenter_ths=0.5,       # Порог центра Y для группировки
            height_ths=0.5,        # Порог высоты
            add_margin=0.1         # Добавить отступ вокруг текста
        )

        names = []

        # Фильтруем: оставляем только строки с буквами (ФИО)
        for (bbox, text, conf) in results:
            # УЛУЧШЕНИЕ 1: Фильтр по confidence score
            # СНИЖЕН порог с 0.4 до 0.3 для печатного текста
            if conf < 0.3:  # Отбрасываем ненадёжное распознавание
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

        # 4. Извлекаем оценки - НОВЫЙ МЕТОД С ДЕТЕКЦИЕЙ ЯЧЕЕК
        print("[INFO] Extracting grades using cell detection...")
        cell_detector = self._get_cell_detector()
        grade_engine = self._get_grade_ocr_engine()

        if cell_detector and grade_engine:
            # Используем новый метод с детекцией ячеек
            grades_grid = self._extract_grades_with_cells(
                image, validated_names, cell_detector, grade_engine
            )
        else:
            # Fallback на старый метод
            print("[INFO] Cell detection unavailable, using fallback method")
            num_students = len(validated_names)
            num_columns = len(dates) if dates else 5
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

    def _extract_grades_with_cells(self, image: np.ndarray, student_names: List[str],
                                   cell_detector, grade_engine) -> List[List[Optional[str]]]:
        """
        Извлечение оценок с использованием детекции ячеек и multi-method OCR

        Args:
            image: Изображение журнала
            student_names: Список имен студентов
            cell_detector: Экземпляр GradeCellDetector
            grade_engine: Экземпляр GradeOCREngine

        Returns:
            Список строк оценок для каждого студента
        """
        # 0. Исправляем перспективу документа
        scanner = self._get_document_scanner()
        if scanner:
            scanned_image, found = scanner.scan_document(image)
            if found:
                print("[INFO] Document perspective corrected")
                image = scanned_image
            else:
                print("[INFO] Document contour not found, using original")

        # 1. Детектируем все ячейки таблицы
        print("[INFO] Detecting table cells...")
        cells = cell_detector.detect_cells(image, names_region_width=0.30)

        if not cells or len(cells) < 10:
            print("[WARNING] Cell detection failed or too few cells detected, using fallback")
            num_columns = 5
            return self._extract_grades_simple(image, len(student_names), num_columns)

        print(f"[INFO] Detected {len(cells)} cells")

        # 2. Фильтруем только ячейки с оценками (пропускаем строки 0 и 1)
        # R0 = заголовок, R1 = даты, R2+ = студенты
        student_cells = [c for c in cells if c['row'] >= 2]

        print(f"[INFO] Filtered to {len(student_cells)} grade cells (rows 2+)")

        # 3. Распознаем оценки из каждой ячейки
        print("[INFO] Recognizing grades from cells...")
        grade_results = []
        for cell in student_cells:
            x, y, w, h = cell['bbox']
            cell_img = image[y:y+h, x:x+w]
            result = grade_engine.recognize_grade(cell_img, cell)
            grade_results.append(result)

        recognized_count = sum(1 for r in grade_results if r['text'])
        print(f"[INFO] Recognized {recognized_count}/{len(grade_results)} grades")

        # 4. Группируем оценки по строкам (row номер соответствует студенту)
        # Строка 2 → студент 0, строка 3 → студент 1, и т.д.
        grades_by_row = {}
        for result in grade_results:
            row = result['cell_info']['row']
            col = result['cell_info']['col']
            grade_text = result['text'] if result['text'] else None

            if row not in grades_by_row:
                grades_by_row[row] = {}
            grades_by_row[row][col] = grade_text

        # 5. Формируем финальную сетку оценок
        result_grid = []
        for student_idx, student_name in enumerate(student_names):
            row_number = student_idx + 2  # Строка 2 для первого студента

            if row_number in grades_by_row:
                row_grades_dict = grades_by_row[row_number]
                # Определяем количество столбцов
                max_col = max(row_grades_dict.keys()) if row_grades_dict else 0
                num_columns = max_col + 1

                # Создаем упорядоченный список оценок
                row_grades = [row_grades_dict.get(col, None) for col in range(num_columns)]
                result_grid.append(row_grades)

                non_empty = sum(1 for g in row_grades if g)
                print(f"[INFO] {student_name}: {non_empty} grades recognized")
            else:
                # Студент без оценок
                result_grid.append([])
                print(f"[INFO] {student_name}: no grades found")

        return result_grid

    def _normalize_name(self, name: str) -> str:
        """
        Нормализация имени для сравнения
        Исправляет типичные ошибки OCR
        """
        # Убираем лишние пробелы
        name = ' '.join(name.split())

        # Приводим к нижнему регистру для сравнения
        name = name.lower()

        # Заменяем ё на е (частая проблема)
        name = name.replace('ё', 'е')

        # Исправление типичных ошибок OCR (латиница/цифры вместо кириллицы)
        replacements = {
            '0': 'о',   # 0 вместо о
            'o': 'о',   # Латинская o
            'O': 'о',   # Латинская O
            'a': 'а',   # Латинская a
            'A': 'а',   # Латинская A
            'e': 'е',   # Латинская e
            'E': 'е',   # Латинская E
            'c': 'с',   # Латинская c
            'C': 'с',   # Латинская C
            'p': 'р',   # Латинская p
            'P': 'р',   # Латинская P
            'x': 'х',   # Латинская x
            'X': 'х',   # Латинская X
            'B': 'в',   # Латинская B
            'H': 'н',   # Латинская H
            'K': 'к',   # Латинская K
            'M': 'м',   # Латинская M
            'T': 'т',   # Латинская T
        }

        for wrong, correct in replacements.items():
            name = name.replace(wrong, correct)

        # Дополнительные замены для частых ошибок Tesseract
        # "В" в начале слова часто распознается вместо "Е"
        if name.startswith('в'):
            # Проверяем следующий символ - если согласная, вероятно должна быть "е"
            if len(name) > 1 and name[1] in 'фтмнлксжшщ':
                name = 'е' + name[1:]

        return name

    def _match_names(self, detected_names: List[str],
                    valid_names: List[str]) -> List[str]:
        """
        Сопоставление распознанных имен с валидным списком
        Использует rapidfuzz для лучшего нечеткого сравнения

        УЛУЧШЕНИЕ: Использует rapidfuzz вместо difflib для лучшей точности
        """
        from rapidfuzz import fuzz, process

        matched = []
        for detected in detected_names:
            # Точное совпадение (быстрый путь)
            if detected in valid_names:
                matched.append(detected)
                print(f"[DEBUG] Exact match: '{detected}'")
                continue

            # Нормализуем для сравнения
            detected_norm = self._normalize_name(detected)
            valid_norm = {self._normalize_name(n): n for n in valid_names}

            # Нечеткое сопоставление с rapidfuzz
            result = process.extractOne(
                detected_norm,
                list(valid_norm.keys()),
                scorer=fuzz.token_sort_ratio,  # Обрабатывает порядок слов
                score_cutoff=70  # Минимальный порог схожести (0-100)
            )

            if result:
                matched_name = valid_norm[result[0]]
                matched.append(matched_name)
                print(f"[DEBUG] Fuzzy match: '{detected}' -> '{matched_name}' (score={result[1]:.0f})")
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
