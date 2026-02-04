"""
Специализированный OCR для распознавания оценок в ячейках
Использует multi-method подход с консенсусом для максимальной точности
"""

import cv2
import numpy as np
import re
from typing import List, Dict, Tuple, Optional
from collections import Counter


# Веса для разных методов OCR (лучшие методы имеют больший вес)
OCR_WEIGHTS = {
    'cnn_classifier': 2.0,   # ЛУЧШИЙ - наш обученный классификатор
    'tesseract_psm10': 1.0,  # Для печатных четких цифр
    'tesseract_psm7': 0.9,   # Универсальный но слабее
    'trocr': 1.5,            # ЛУЧШИЙ для рукописного текста (Microsoft transformer)
    'easyocr': 1.2           # Хороший для рукописи
}


class GradeOCREngine:
    """
    Распознавание оценок из отдельных ячеек таблицы
    Использует множественные методы и консенсус для максимальной точности
    """

    def __init__(self, debug: bool = False):
        """
        Args:
            debug: Если True, сохраняет промежуточные изображения и логи
        """
        self.debug = debug
        self.tesseract = None
        self.easyocr_reader = None
        self.trocr_processor = None
        self.trocr_model = None
        self.cnn_classifier = None

        # Ленивая инициализация CNN классификатора (приоритетный метод)
        self._ensure_cnn_classifier()

        # Ленивая инициализация Tesseract
        try:
            import pytesseract
            self.tesseract = pytesseract
            print("[INFO] Tesseract initialized for grade recognition")
        except Exception as e:
            print(f"[WARNING] Tesseract initialization failed: {e}")

    def _ensure_cnn_classifier(self):
        """Ленивая инициализация CNN классификатора"""
        if self.cnn_classifier is None:
            try:
                from .grade_classifier import GradeClassifier
                classifier = GradeClassifier()
                if classifier.is_available():
                    self.cnn_classifier = classifier
                    print("[INFO] CNN classifier initialized (primary method)")
                else:
                    print("[INFO] CNN classifier not available, using fallback methods")
            except Exception as e:
                print(f"[WARNING] CNN classifier initialization failed: {e}")

    def _ensure_easyocr(self):
        """Ленивая инициализация EasyOCR"""
        if self.easyocr_reader is None:
            try:
                import easyocr
                self.easyocr_reader = easyocr.Reader(['ru'], gpu=False)
                print("[INFO] EasyOCR initialized for fallback")
            except Exception as e:
                print(f"[WARNING] EasyOCR initialization failed: {e}")

    def _ensure_trocr(self):
        """Ленивая инициализация TrOCR (Microsoft handwriting model)"""
        if self.trocr_processor is None or self.trocr_model is None:
            try:
                from transformers import TrOCRProcessor, VisionEncoderDecoderModel
                print("[INFO] Loading TrOCR model (first time may take a few minutes)...")

                # Используем предобученную модель для рукописного текста
                self.trocr_processor = TrOCRProcessor.from_pretrained('microsoft/trocr-small-handwritten')
                self.trocr_model = VisionEncoderDecoderModel.from_pretrained('microsoft/trocr-small-handwritten')

                print("[INFO] TrOCR initialized successfully")
            except Exception as e:
                print(f"[WARNING] TrOCR initialization failed: {e}")

    def recognize_grade(self, cell_image: np.ndarray, cell_info: Dict) -> Dict:
        """
        Распознать оценку из ячейки используя множественные методы

        Args:
            cell_image: Изображение ячейки
            cell_info: Информация о ячейке (row, col, bbox, center_y)

        Returns:
            {
                'text': str,              # Распознанная оценка
                'confidence': float,      # Уверенность (0-100)
                'method': str,            # Использованный метод(ы)
                'needs_review': bool,     # Нужна ли проверка учителем
                'alternatives': List[str] # Альтернативные варианты
            }
        """
        if self.debug:
            row, col = cell_info.get('row', -1), cell_info.get('col', -1)
            cv2.imwrite(f'debug_grade_r{row}_c{col}_00_original.jpg', cell_image)

        results = []

        # 0. CNN Classifier - ПРИОРИТЕТНЫЙ метод (если доступен)
        if self.cnn_classifier:
            cnn_result = self.cnn_classifier.classify_with_alternatives(cell_image)
            cnn_text = cnn_result['text']
            cnn_conf = cnn_result['confidence']

            if cnn_conf >= 90:
                # Высокая уверенность CNN - возвращаем сразу без других методов
                if self.debug:
                    print(f"[DEBUG] Cell R{cell_info.get('row')}C{cell_info.get('col')}: "
                          f"CNN HIGH CONF '{cnn_text}' confidence={cnn_conf:.1f}")
                return {
                    'text': cnn_text,
                    'confidence': cnn_conf,
                    'method': 'cnn_classifier',
                    'needs_review': False,
                    'alternatives': [alt[0] for alt in cnn_result['alternatives']],
                    'cell_info': cell_info
                }

            # Средняя уверенность - добавляем к results для консенсуса
            if cnn_text and cnn_conf >= 50:
                results.append(('cnn_classifier', cnn_text, cnn_conf, 'cnn'))

        # 1. Попробовать 3 варианта предобработки
        for variant in ['standard', 'high_contrast', 'inverted']:
            preprocessed = self._preprocess_variants(cell_image, variant)

            if self.debug:
                row, col = cell_info.get('row', -1), cell_info.get('col', -1)
                cv2.imwrite(f'debug_grade_r{row}_c{col}_prep_{variant}.jpg', preprocessed)

            # 2. Tesseract PSM 7 (single line) - ПРИОРИТЕТ для рукописного
            if self.tesseract:
                text_t7, conf_t7 = self._tesseract_psm7(preprocessed)
                if conf_t7 >= 60:  # Повышен порог обратно до 60
                    results.append(('tesseract_psm7', text_t7, conf_t7, variant))

            # 3. Tesseract PSM 10 (single character)
            if self.tesseract:
                text_t10, conf_t10 = self._tesseract_psm10(preprocessed)
                if conf_t10 >= 70:  # Повышен порог обратно до 70
                    results.append(('tesseract_psm10', text_t10, conf_t10, variant))

        # 4. EasyOCR на всех вариантах предобработки (лучше для рукописи)
        for variant in ['standard', 'high_contrast', 'inverted']:
            preprocessed = self._preprocess_variants(cell_image, variant)
            text_easy, conf_easy = self._easyocr_extract(preprocessed)
            if conf_easy >= 40:  # Снижен порог для EasyOCR
                results.append(('easyocr', text_easy, conf_easy, variant))

        # 5. Нормализовать все результаты
        normalized_results = []
        for method, text, conf, variant in results:
            normalized = self._normalize_grade_text(text)
            if self._is_valid_grade_pattern(normalized):
                normalized_results.append((method, normalized, conf, variant))

        if not normalized_results:
            if self.debug:
                print(f"[DEBUG] Cell R{cell_info.get('row')}C{cell_info.get('col')}: No valid results")
            return {
                'text': '',
                'confidence': 0,
                'method': 'failed',
                'needs_review': True,
                'alternatives': [],
                'cell_info': cell_info
            }

        # 6. Консенсус: если несколько методов дают одинаковый результат - высокая уверенность
        consensus = self._find_consensus(normalized_results)
        if consensus:
            if self.debug:
                print(f"[DEBUG] Cell R{cell_info.get('row')}C{cell_info.get('col')}: "
                      f"CONSENSUS '{consensus['text']}' confidence={consensus['confidence']:.1f}")
            return {
                'text': consensus['text'],
                'confidence': consensus['confidence'],
                'method': consensus['methods'],
                'needs_review': False,
                'alternatives': [],
                'cell_info': cell_info
            }

        # 7. Нет консенсуса - используем взвешенное голосование
        weighted_result = self._weighted_consensus(normalized_results)

        if self.debug:
            print(f"[DEBUG] Cell R{cell_info.get('row')}C{cell_info.get('col')}: "
                  f"WEIGHTED '{weighted_result['text']}' confidence={weighted_result['confidence']:.1f}")

        return {
            'text': weighted_result['text'],
            'confidence': weighted_result['confidence'],
            'method': weighted_result['method'],
            'needs_review': weighted_result['confidence'] < 85,
            'alternatives': weighted_result['alternatives'],
            'cell_info': cell_info
        }

    def _preprocess_variants(self, cell_image: np.ndarray, variant: str) -> np.ndarray:
        """
        3 варианта предобработки для разных условий освещения
        """
        if variant == 'standard':
            return self._preprocess_standard(cell_image)
        elif variant == 'high_contrast':
            return self._preprocess_high_contrast(cell_image)
        elif variant == 'inverted':
            return self._preprocess_inverted(cell_image)
        else:
            return self._preprocess_standard(cell_image)

    def _preprocess_standard(self, cell_image: np.ndarray) -> np.ndarray:
        """Стандартная предобработка"""
        # 1. Resize 5x (INTER_CUBIC) - увеличил с 3x для маленьких ячеек
        scale = 5
        h, w = cell_image.shape[:2]
        resized = cv2.resize(cell_image, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)

        # 2. Grayscale
        if len(resized.shape) == 3:
            gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
        else:
            gray = resized.copy()

        # 3. CLAHE (clipLimit=2.0, tileGridSize=(4,4))
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)

        # 4. Деноизинг (h=7)
        denoised = cv2.fastNlMeansDenoising(enhanced, None, h=7)

        # 5. Otsu binarization
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 6. Белая рамка 10px (помогает Tesseract)
        border_size = 10
        bordered = cv2.copyMakeBorder(binary, border_size, border_size, border_size, border_size,
                                     cv2.BORDER_CONSTANT, value=255)

        return bordered

    def _preprocess_high_contrast(self, cell_image: np.ndarray) -> np.ndarray:
        """Для слабого контраста - более агрессивная CLAHE"""
        # Конвертируем в grayscale
        if len(cell_image.shape) == 3:
            gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = cell_image.copy()

        # Масштабируем 5x
        scaled = cv2.resize(gray, None, fx=5, fy=5, interpolation=cv2.INTER_CUBIC)

        # Более агрессивная CLAHE
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(scaled)

        # Рамка
        bordered = cv2.copyMakeBorder(enhanced, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=255)

        return bordered

    def _preprocess_inverted(self, cell_image: np.ndarray) -> np.ndarray:
        """Для светлого текста на темном фоне (инверсия)"""
        standard = self._preprocess_standard(cell_image)
        inverted = cv2.bitwise_not(standard)
        return inverted

    def _tesseract_psm10(self, preprocessed: np.ndarray) -> Tuple[str, float]:
        """Tesseract с PSM 10 (single character)"""
        if not self.tesseract:
            return '', 0.0

        try:
            config = '--psm 10 -c tessedit_char_whitelist=012345нбНБ1'
            data = self.tesseract.image_to_data(
                preprocessed,
                lang='rus',
                config=config,
                output_type=self.tesseract.Output.DICT
            )

            # Извлекаем текст с максимальной уверенностью
            texts = [t.strip() for t in data['text'] if t.strip()]
            confs = [float(c) for c, t in zip(data['conf'], data['text']) if t.strip() and float(c) >= 0]

            if texts and confs:
                best_idx = confs.index(max(confs))
                return texts[best_idx], confs[best_idx]

        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Tesseract PSM10 error: {e}")

        return '', 0.0

    def _tesseract_psm7(self, preprocessed: np.ndarray) -> Tuple[str, float]:
        """Tesseract с PSM 7 (single line)"""
        if not self.tesseract:
            return '', 0.0

        try:
            config = '--psm 7 -c tessedit_char_whitelist=012345нбНБ1'
            text = self.tesseract.image_to_string(preprocessed, lang='rus', config=config)
            text = text.strip()

            # Для PSM 7 используем фиксированную confidence 65%
            if text:
                return text, 65.0

        except Exception as e:
            if self.debug:
                print(f"[DEBUG] Tesseract PSM7 error: {e}")

        return '', 0.0

    def _easyocr_extract(self, cell_image: np.ndarray) -> Tuple[str, float]:
        """Извлечение с помощью EasyOCR"""
        self._ensure_easyocr()

        if not self.easyocr_reader:
            return '', 0.0

        try:
            # EasyOCR лучше работает с умеренной предобработкой
            preprocessed = self._preprocess_high_contrast(cell_image)

            results = self.easyocr_reader.readtext(
                preprocessed,
                detail=1,
                paragraph=False,
                min_size=3,           # Снижено с 5 для маленьких ячеек
                text_threshold=0.2,   # Снижено с 0.5 для низкой уверенности
                low_text=0.1,         # Снижено с 0.3
                allowlist='0123456789нбНБ'  # Только валидные символы для оценок
            )

            if results:
                # Берем результат с максимальной уверенностью
                best = max(results, key=lambda x: x[2])
                return best[1].strip(), best[2] * 100

        except Exception as e:
            if self.debug:
                print(f"[DEBUG] EasyOCR error: {e}")

        return '', 0.0

    def _trocr_extract(self, cell_image: np.ndarray) -> Tuple[str, float]:
        """Извлечение с помощью TrOCR (Microsoft handwriting model)"""
        self._ensure_trocr()

        if not self.trocr_processor or not self.trocr_model:
            return '', 0.0

        try:
            from PIL import Image

            # Конвертируем в PIL Image
            if len(cell_image.shape) == 2:
                # Grayscale -> RGB
                cell_rgb = cv2.cvtColor(cell_image, cv2.COLOR_GRAY2RGB)
            else:
                cell_rgb = cv2.cvtColor(cell_image, cv2.COLOR_BGR2RGB)

            pil_image = Image.fromarray(cell_rgb)

            # Предобработка для TrOCR - увеличиваем и улучшаем контраст
            preprocessed = self._preprocess_high_contrast(cell_image)
            preprocessed_rgb = cv2.cvtColor(preprocessed, cv2.COLOR_GRAY2RGB) if len(preprocessed.shape) == 2 else preprocessed
            pil_preprocessed = Image.fromarray(preprocessed_rgb)

            # Обработка через TrOCR
            pixel_values = self.trocr_processor(images=pil_preprocessed, return_tensors="pt").pixel_values
            generated_ids = self.trocr_model.generate(pixel_values)
            text = self.trocr_processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

            # TrOCR не дает confidence напрямую, используем фиксированное значение 75%
            confidence = 75.0

            return text.strip(), confidence

        except Exception as e:
            if self.debug:
                print(f"[DEBUG] TrOCR error: {e}")

        return '', 0.0

    def _normalize_grade_text(self, text: str) -> str:
        """Нормализация текста оценки"""
        if not text:
            return ''

        # Убираем пробелы и пунктуацию
        text = re.sub(r'[^\wА-Яа-яЁё]', '', text)

        # Приводим к нижнему регистру
        text = text.lower()

        # Замены похожих символов
        replacements = {
            'з': '3', 'З': '3',  # Cyrillic З → 3
            'о': '0', 'О': '0',  # Cyrillic О → 0 (НО в оценках 0 не бывает!)
            'б': 'б', 'Б': 'б',  # Нормализуем к lowercase
            's': '5', 'S': '5',  # Latin S → 5
            'i': '1', 'I': '1', 'l': '1',  # Latin I/l → 1
            'h': 'н', 'H': 'н',  # Latin H → Cyrillic н
            'н': 'н', 'Н': 'н',  # Нормализуем н
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        # Убираем дубли одинаковых цифр (55 → 5, 33 → 3, 44 → 4)
        if len(text) == 2 and text[0] == text[1] and text[0].isdigit():
            text = text[0]

        # Если несколько РАЗНЫХ цифр подряд (например "53", "13", "51") - берем только первую
        if len(text) >= 2:
            # Если первый символ - цифра, а второй - тоже цифра (но не н/б)
            if text[0].isdigit() and text[1].isdigit():
                text = text[0]  # Берем только первую цифру

        # Убираем лишние символы, оставляем только первые 1-2 символа
        if len(text) > 2:
            text = text[:2]

        return text

    def _is_valid_grade_pattern(self, text: str) -> bool:
        """Валидация оценки с помощью regex"""
        if not text:
            return False

        # Валидные паттерны: 1, 2, 3, 4, 5, н, б, нн
        pattern = r'^[1-5нб]{1,2}$'

        if re.match(pattern, text):
            return True

        if self.debug and text:
            print(f"[DEBUG] REJECTED: '{text}' doesn't match pattern")

        return False

    def _find_consensus(self, results: List[Tuple]) -> Optional[Dict]:
        """
        Найти консенсус между методами
        Если хотя бы 2 метода согласны - это консенсус
        """
        texts = [r[1] for r in results]
        counter = Counter(texts)

        most_common = counter.most_common(1)[0]

        # Консенсус = минимум 2 метода согласны
        if most_common[1] >= 2:
            agreeing = [r for r in results if r[1] == most_common[0]]
            avg_conf = sum(r[2] for r in agreeing) / len(agreeing)

            # Бонус за консенсус (+15%)
            final_conf = min(95, avg_conf + 15)

            methods = '+'.join(set(r[0] for r in agreeing))

            return {
                'text': most_common[0],
                'confidence': final_conf,
                'methods': methods
            }

        return None

    def _weighted_consensus(self, results: List[Tuple]) -> Dict:
        """
        Взвешенное голосование между методами
        Используется когда нет прямого консенсуса
        """
        scores = {}

        for method, text, conf, variant in results:
            weight = OCR_WEIGHTS.get(method, 1.0)
            weighted_conf = conf * weight

            if text not in scores:
                scores[text] = []
            scores[text].append((method, weighted_conf))

        # Выбираем текст с максимальной суммой взвешенных confidence
        best_item = max(scores.items(), key=lambda x: sum(c for _, c in x[1]))
        best_text = best_item[0]
        best_scores = best_item[1]

        # Средняя взвешенная уверенность
        avg_weighted_conf = sum(c for _, c in best_scores) / len(best_scores)

        # Список альтернатив
        alternatives = [text for text in scores.keys() if text != best_text]

        # Метод
        methods = '+'.join(set(m for m, _ in best_scores))

        return {
            'text': best_text,
            'confidence': min(95, avg_weighted_conf),
            'method': methods,
            'alternatives': alternatives
        }
