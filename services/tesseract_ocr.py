"""
Tesseract OCR для печатного текста (имена в журналах)
Tesseract обычно работает лучше чем EasyOCR для печатного текста
"""

import cv2
import numpy as np
from typing import List, Optional
import re

# Ленивый импорт pytesseract
_pytesseract = None


def get_tesseract():
    """Ленивая инициализация pytesseract"""
    global _pytesseract
    if _pytesseract is None:
        try:
            import pytesseract
            _pytesseract = pytesseract
            print("[INFO] Tesseract OCR initialized")
        except ImportError:
            print("[WARNING] pytesseract not installed. Install with: pip install pytesseract")
            print("[WARNING] Also install Tesseract: brew install tesseract (Mac) or apt install tesseract-ocr (Linux)")
            return None
    return _pytesseract


class TesseractNameExtractor:
    """
    Извлечение имен студентов с помощью Tesseract OCR
    Оптимизировано для печатного кириллического текста
    """

    def __init__(self):
        self.tesseract = get_tesseract()

    def is_available(self) -> bool:
        """Проверить доступность Tesseract"""
        return self.tesseract is not None

    def extract_names(self, image: np.ndarray, names_region_width: float = 0.30) -> List[str]:
        """
        Извлечь имена студентов из левой части изображения

        Args:
            image: Изображение журнала
            names_region_width: Ширина области с именами (0.30 = 30% от ширины)

        Returns:
            Список имен студентов
        """
        if not self.is_available():
            print("[WARNING] Tesseract not available, returning empty list")
            return []

        # НОВОЕ: Сначала попробуем найти и выровнять документ
        # НО только если изображение цветное (не предобработанное)
        if len(image.shape) == 3:  # Цветное изображение
            try:
                from .document_scanner import DocumentScanner
                scanner = DocumentScanner()
                scanned, found = scanner.scan_document(image)
                if found:
                    print("[INFO] Document scanned and perspective corrected")
                    image = scanned
            except Exception as e:
                print(f"[WARNING] Document scanning failed: {e}, using original")
        else:
            print("[INFO] Image is already preprocessed (grayscale), skipping document scanning")

        # Берем левую часть изображения (где обычно ФИО)
        height, width = image.shape[:2]
        names_region = image[:, 0:int(width * names_region_width)]

        # Предобработка для Tesseract
        preprocessed = self._preprocess_for_names(names_region)

        # Конфигурация Tesseract для русского языка
        # PSM 4 = assume a single column of text of variable sizes (ЛУЧШЕ ДЛЯ ТАБЛИЦ)
        # PSM 6 = assume a single uniform block of text
        # OEM 3 = Default, based on what is available (best)
        custom_config = r'--oem 3 --psm 4 -l rus'  # ИЗМЕНЕНО с PSM 6 на PSM 4

        try:
            # Извлечение текста
            text = self.tesseract.image_to_string(preprocessed, config=custom_config)

            # Также получаем детальные данные с координатами
            data = self.tesseract.image_to_data(
                preprocessed,
                config=custom_config,
                output_type=self.tesseract.Output.DICT
            )

            # Извлекаем имена с координатами для сортировки
            names_with_y = []

            # Группируем слова в строки по Y-координате
            lines = {}
            for i in range(len(data['text'])):
                text_item = data['text'][i].strip()
                conf = int(data['conf'][i])

                # Фильтруем по confidence (убираем фильтр по длине)
                if conf > 15 and len(text_item) >= 2:
                    # Пропускаем заголовки
                    if 'класс' in text_item.lower() or 'фио' in text_item.lower():
                        continue

                    # Пропускаем номера
                    if re.match(r'^\d+\.?$', text_item):
                        continue

                    y_coord = data['top'][i]
                    x_coord = data['left'][i]

                    # Группируем по Y-координате (УВЕЛИЧЕН допуск для лучшей группировки)
                    found_line = False
                    for line_y in lines:
                        if abs(y_coord - line_y) < 40:  # Было 20, стало 40
                            lines[line_y].append((x_coord, text_item, conf))
                            found_line = True
                            break

                    if not found_line:
                        lines[y_coord] = [(x_coord, text_item, conf)]

            # Собираем имена из каждой строки
            for y_coord in sorted(lines.keys()):
                # Сортируем слова в строке по X-координате
                words_in_line = sorted(lines[y_coord], key=lambda x: x[0])

                # Объединяем ТОЛЬКО первые 2-3 слова (фамилия + имя + возможно отчество)
                # Это предотвратит захват оценок
                words_to_use = []
                for i, (x, word, conf) in enumerate(words_in_line):
                    if i < 3:  # Максимум 3 слова
                        # Проверяем что это не оценка
                        if not word.isdigit() and word not in ['н', 'б', 'н/н']:
                            words_to_use.append(word)

                full_name = ' '.join(words_to_use)

                # Нормализуем имя
                full_name = self._normalize_name(full_name)

                # Добавляем любое имя длиннее 3 символов (rapidfuzz исправит)
                if full_name and len(full_name) >= 3:
                    names_with_y.append((y_coord, full_name))

            # Сортируем по Y-координате (сверху вниз)
            names_with_y.sort(key=lambda x: x[0])

            # Возвращаем только имена
            names = [name for (y, name) in names_with_y]

            print(f"[INFO] Tesseract extracted {len(names)} names")
            return names

        except Exception as e:
            print(f"[ERROR] Tesseract extraction failed: {e}")
            return []

    def _preprocess_for_names(self, image: np.ndarray) -> np.ndarray:
        """
        Предобработка изображения для лучшего распознавания имен Tesseract
        УПРОЩЁННАЯ версия - Tesseract лучше работает с grayscale БЕЗ бинаризации
        """
        # Конвертируем в grayscale если нужно
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Увеличиваем размер (Tesseract работает лучше на больших изображениях)
        scale_factor = 2.5
        gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor,
                         interpolation=cv2.INTER_CUBIC)

        # Улучшение контраста с CLAHE (умеренное)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Лёгкий denoise (не убивает детали)
        denoised = cv2.fastNlMeansDenoising(enhanced, None, h=10)

        # Небольшое увеличение контраста
        result = cv2.convertScaleAbs(denoised, alpha=1.1, beta=5)

        # ВАЖНО: Возвращаем grayscale, НЕ бинаризованное изображение
        # Tesseract сам лучше справится с определением порогов
        return result

    def _normalize_name(self, name: str) -> str:
        """
        Нормализация имени
        """
        # Убираем лишние пробелы
        name = ' '.join(name.split())

        # Исправление типичных ошибок OCR
        replacements = {
            '0': 'О',
            'o': 'о',
            'O': 'О',
            'a': 'а',
            'A': 'А',
            'e': 'е',
            'E': 'Е',
            'c': 'с',
            'C': 'С',
            'p': 'р',
            'P': 'Р',
            'x': 'х',
            'X': 'Х',
            'B': 'В',
            'H': 'Н',
            'K': 'К',
            'M': 'М',
            'T': 'Т',
        }

        for wrong, correct in replacements.items():
            name = name.replace(wrong, correct)

        # Правильное капитализирование
        name = ' '.join(word.capitalize() for word in name.split())

        # Удаление не-кириллических символов (кроме пробелов и дефисов)
        name = re.sub(r'[^а-яА-ЯёЁ\s\-]', '', name)

        return name.strip()
