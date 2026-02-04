"""
Классификатор оценок на основе CNN
Использует ONNX Runtime для быстрого inference
"""

import os
import json
import cv2
import numpy as np
from typing import Tuple, Optional, Dict

# Путь к модели по умолчанию
DEFAULT_MODEL_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'grade_classifier.onnx')
DEFAULT_METADATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'models', 'grade_classifier_metadata.json')


class GradeClassifier:
    """
    CNN классификатор для распознавания оценок
    Классы: 1, 2, 3, 4, 5, empty (позже добавим н, б)
    """

    def __init__(self, model_path: str = None, metadata_path: str = None):
        """
        Args:
            model_path: Путь к ONNX модели
            metadata_path: Путь к JSON с метаданными
        """
        self.model_path = model_path or DEFAULT_MODEL_PATH
        self.metadata_path = metadata_path or DEFAULT_METADATA_PATH

        self.session = None
        self.classes = ['1', '2', '3', '4', '5', 'empty']
        self.img_size = 28

        # Загружаем метаданные если есть
        self._load_metadata()

    def _load_metadata(self):
        """Загрузить метаданные модели"""
        if os.path.exists(self.metadata_path):
            try:
                with open(self.metadata_path, 'r') as f:
                    metadata = json.load(f)
                    self.classes = metadata.get('classes', self.classes)
                    self.img_size = metadata.get('img_size', self.img_size)
                    print(f"[GradeClassifier] Загружены метаданные: {len(self.classes)} классов")
            except Exception as e:
                print(f"[GradeClassifier] Ошибка загрузки метаданных: {e}")

    def _ensure_model(self):
        """Ленивая загрузка модели"""
        if self.session is not None:
            return True

        if not os.path.exists(self.model_path):
            print(f"[GradeClassifier] Модель не найдена: {self.model_path}")
            print("[GradeClassifier] Запустите scripts/prepare_dataset.py и scripts/train_classifier.py")
            return False

        try:
            import onnxruntime as ort
            self.session = ort.InferenceSession(self.model_path)
            print(f"[GradeClassifier] Модель загружена: {self.model_path}")
            return True
        except ImportError:
            print("[GradeClassifier] Установите onnxruntime: pip install onnxruntime")
            return False
        except Exception as e:
            print(f"[GradeClassifier] Ошибка загрузки модели: {e}")
            return False

    def preprocess(self, cell_image: np.ndarray) -> np.ndarray:
        """
        Предобработка изображения ячейки для классификатора

        Args:
            cell_image: Изображение ячейки (BGR или grayscale)

        Returns:
            Тензор формата [1, 1, 28, 28]
        """
        # Конвертируем в grayscale если нужно
        if len(cell_image.shape) == 3:
            gray = cv2.cvtColor(cell_image, cv2.COLOR_BGR2GRAY)
        else:
            gray = cell_image.copy()

        # Resize до нужного размера
        resized = cv2.resize(gray, (self.img_size, self.img_size), interpolation=cv2.INTER_AREA)

        # Нормализация как в MNIST: инвертируем (темный текст на белом фоне -> светлый на темном)
        # MNIST: черный фон (0), белые цифры (255)
        # Наши фото: белый фон, темные цифры
        # Поэтому инвертируем
        inverted = 255 - resized

        # Нормализация к [-1, 1] (как при обучении)
        normalized = (inverted.astype(np.float32) / 255.0 - 0.5) / 0.5

        # Добавляем размерности batch и channel
        tensor = normalized.reshape(1, 1, self.img_size, self.img_size)

        return tensor

    def classify(self, cell_image: np.ndarray) -> Tuple[str, float]:
        """
        Классифицировать изображение ячейки

        Args:
            cell_image: Изображение ячейки

        Returns:
            (class_name, confidence) - название класса и уверенность 0-100
        """
        if not self._ensure_model():
            return '', 0.0

        try:
            # Предобработка
            input_tensor = self.preprocess(cell_image)

            # Inference
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: input_tensor})

            # Softmax для получения вероятностей
            logits = outputs[0][0]
            exp_logits = np.exp(logits - np.max(logits))  # Numerical stability
            probabilities = exp_logits / exp_logits.sum()

            # Находим класс с максимальной вероятностью
            class_idx = np.argmax(probabilities)
            confidence = probabilities[class_idx] * 100

            class_name = self.classes[class_idx]

            return class_name, confidence

        except Exception as e:
            print(f"[GradeClassifier] Ошибка классификации: {e}")
            return '', 0.0

    def classify_with_alternatives(self, cell_image: np.ndarray, top_k: int = 3) -> Dict:
        """
        Классифицировать с возвратом альтернативных вариантов

        Args:
            cell_image: Изображение ячейки
            top_k: Количество топ вариантов

        Returns:
            {
                'text': str,              # Лучший класс
                'confidence': float,      # Уверенность 0-100
                'alternatives': list,     # Альтернативные варианты [(class, conf), ...]
                'needs_review': bool      # Нужна ли проверка
            }
        """
        if not self._ensure_model():
            return {
                'text': '',
                'confidence': 0.0,
                'alternatives': [],
                'needs_review': True
            }

        try:
            # Предобработка
            input_tensor = self.preprocess(cell_image)

            # Inference
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: input_tensor})

            # Softmax
            logits = outputs[0][0]
            exp_logits = np.exp(logits - np.max(logits))
            probabilities = exp_logits / exp_logits.sum()

            # Сортируем по убыванию вероятности
            sorted_indices = np.argsort(probabilities)[::-1]

            best_idx = sorted_indices[0]
            best_class = self.classes[best_idx]
            best_conf = probabilities[best_idx] * 100

            # Альтернативы (кроме лучшего)
            alternatives = []
            for idx in sorted_indices[1:top_k]:
                alt_class = self.classes[idx]
                alt_conf = probabilities[idx] * 100
                if alt_conf > 5:  # Только значимые альтернативы
                    alternatives.append((alt_class, alt_conf))

            # Нужна проверка если уверенность низкая или много альтернатив
            needs_review = best_conf < 85 or (len(alternatives) > 0 and alternatives[0][1] > 20)

            return {
                'text': best_class if best_class != 'empty' else '',
                'confidence': best_conf,
                'alternatives': alternatives,
                'needs_review': needs_review
            }

        except Exception as e:
            print(f"[GradeClassifier] Ошибка классификации: {e}")
            return {
                'text': '',
                'confidence': 0.0,
                'alternatives': [],
                'needs_review': True
            }

    def is_available(self) -> bool:
        """Проверить доступность модели"""
        return os.path.exists(self.model_path)


# Глобальный экземпляр для переиспользования
_classifier_instance: Optional[GradeClassifier] = None


def get_classifier() -> GradeClassifier:
    """Получить singleton экземпляр классификатора"""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = GradeClassifier()
    return _classifier_instance
