"""
Обработка изображений перед OCR
Коррекция перспективы, улучшение качества, бинаризация
"""
import cv2
import numpy as np
from typing import Tuple, Optional


class ImageProcessor:
    def __init__(self):
        pass

    def load_image(self, image_path: str) -> np.ndarray:
        """Загрузить изображение"""
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Cannot load image from {image_path}")
        return image

    def resize_if_large(self, image: np.ndarray, max_width: int = 2000) -> np.ndarray:
        """
        Уменьшить изображение если оно слишком большое
        (для ускорения обработки)
        """
        height, width = image.shape[:2]
        if width > max_width:
            scale = max_width / width
            new_width = max_width
            new_height = int(height * scale)
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        return image

    def convert_to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Конвертация в оттенки серого"""
        if len(image.shape) == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return image

    def improve_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Улучшение контрастности с помощью CLAHE
        (Contrast Limited Adaptive Histogram Equalization)

        УЛУЧШЕНИЕ 4: Увеличен clipLimit с 2.0 до 3.0 для лучшей читаемости текста
        """
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        return clahe.apply(image)

    def denoise(self, image: np.ndarray) -> np.ndarray:
        """Удаление шумов"""
        return cv2.fastNlMeansDenoising(image, h=10)

    def binarize(self, image: np.ndarray) -> np.ndarray:
        """
        Бинаризация (черно-белое изображение)
        Использует adaptive threshold для лучших результатов
        """
        binary = cv2.adaptiveThreshold(
            image,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            11,
            2
        )
        return binary

    def enhance_for_handwriting(self, image: np.ndarray) -> np.ndarray:
        """
        Специальная обработка для РУКОПИСНОГО текста

        Применяет:
        - Увеличение разрешения (super-resolution)
        - Морфологические операции для утолщения линий
        - Агрессивную бинаризацию
        """
        # 1. Увеличение разрешения в 2 раза
        upscaled = cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        # 2. Агрессивная фильтрация шумов
        denoised = cv2.fastNlMeansDenoising(upscaled, h=15)

        # 3. Усиление контраста (более агрессивное для рукописи)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
        contrast_enhanced = clahe.apply(denoised)

        # 4. Морфологическое утолщение линий (помогает с тонкими линиями рукописи)
        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(contrast_enhanced, kernel, iterations=1)

        # 5. Адаптивная бинаризация с большим блоком
        binary = cv2.adaptiveThreshold(
            dilated,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            15,  # Больший блок для рукописи
            3    # Больше порог
        )

        # 6. Удаление мелких артефактов
        kernel_clean = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel_clean)

        return cleaned

    def detect_rotation(self, image: np.ndarray) -> float:
        """
        Определение угла поворота изображения
        Возвращает угол в градусах
        """
        # Используем детекцию линий для определения угла
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)

        if lines is None:
            return 0.0

        angles = []
        for line in lines[:20]:  # Берем первые 20 линий
            rho, theta = line[0]
            angle = np.degrees(theta) - 90
            if abs(angle) < 45:  # Игнорируем слишком большие углы
                angles.append(angle)

        if angles:
            # Медианный угол
            return float(np.median(angles))

        return 0.0

    def rotate_image(self, image: np.ndarray, angle: float) -> np.ndarray:
        """Поворот изображения на заданный угол"""
        if abs(angle) < 0.5:  # Если угол меньше 0.5 градусов, не поворачиваем
            return image

        height, width = image.shape[:2]
        center = (width // 2, height // 2)

        # Матрица поворота
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)

        # Вычисляем новые размеры
        cos = np.abs(rotation_matrix[0, 0])
        sin = np.abs(rotation_matrix[0, 1])
        new_width = int((height * sin) + (width * cos))
        new_height = int((height * cos) + (width * sin))

        # Корректируем матрицу для нового размера
        rotation_matrix[0, 2] += (new_width / 2) - center[0]
        rotation_matrix[1, 2] += (new_height / 2) - center[1]

        # Поворачиваем
        rotated = cv2.warpAffine(image, rotation_matrix, (new_width, new_height),
                                 flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

        return rotated

    def detect_table_contours(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Детекция границ таблицы
        Возвращает координаты углов таблицы
        """
        # Детекция границ
        edges = cv2.Canny(image, 50, 150)

        # Морфологические операции для улучшения контуров
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)

        # Поиск контуров
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # Находим самый большой прямоугольный контур
        largest_contour = max(contours, key=cv2.contourArea)

        # Аппроксимируем контур
        epsilon = 0.02 * cv2.arcLength(largest_contour, True)
        approx = cv2.approxPolyDP(largest_contour, epsilon, True)

        if len(approx) == 4:
            return approx.reshape(4, 2)

        # Если не получилось найти 4 угла, возвращаем bounding rect
        x, y, w, h = cv2.boundingRect(largest_contour)
        return np.array([[x, y], [x + w, y], [x + w, y + h], [x, y + h]])

    def correct_perspective(self, image: np.ndarray, corners: np.ndarray) -> np.ndarray:
        """
        Коррекция перспективы (если фото под углом)
        corners: 4 точки углов таблицы
        """
        # Сортировка углов: top-left, top-right, bottom-right, bottom-left
        rect = self._order_points(corners)

        (tl, tr, br, bl) = rect

        # Вычисляем ширину
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        # Вычисляем высоту
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        # Целевые точки
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")

        # Матрица трансформации
        M = cv2.getPerspectiveTransform(rect, dst)

        # Применяем трансформацию
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

        return warped

    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """Сортировка точек: top-left, top-right, bottom-right, bottom-left"""
        rect = np.zeros((4, 2), dtype="float32")

        # Сумма координат
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # top-left
        rect[2] = pts[np.argmax(s)]  # bottom-right

        # Разность координат
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # top-right
        rect[3] = pts[np.argmax(diff)]  # bottom-left

        return rect

    def preprocess_for_ocr(self, image_path: str, save_debug: bool = False) -> np.ndarray:
        """
        Полная предобработка изображения для OCR
        Главная функция, которая вызывает все остальные

        Этапы:
        1. Загрузка
        2. Уменьшение размера если нужно
        3. Конвертация в grayscale
        4. Определение и исправление поворота
        5. Детекция таблицы и коррекция перспективы (опционально)
        6. Улучшение контрастности
        7. Удаление шумов
        8. Бинаризация
        """
        # 1. Загрузка
        image = self.load_image(image_path)

        # 2. Уменьшение
        image = self.resize_if_large(image)

        # 3. Grayscale
        gray = self.convert_to_grayscale(image)

        # 4. Определение и исправление поворота
        angle = self.detect_rotation(gray)
        if abs(angle) > 0.5:
            gray = self.rotate_image(gray, angle)
            print(f"[INFO] Image rotated by {angle:.2f} degrees")

        # 5. Детекция и коррекция перспективы (опционально)
        # Это может быть слишком агрессивно, поэтому делаем осторожно
        try:
            corners = self.detect_table_contours(gray)
            if corners is not None:
                # Проверяем что это действительно прямоугольник
                area = cv2.contourArea(corners)
                image_area = gray.shape[0] * gray.shape[1]
                if area > image_area * 0.5:  # Таблица занимает больше 50% изображения
                    gray = self.correct_perspective(gray, corners)
                    print("[INFO] Perspective corrected")
        except Exception as e:
            print(f"[WARNING] Perspective correction failed: {e}")

        # 6. Улучшение контрастности
        enhanced = self.improve_contrast(gray)

        # 7-8. Два режима обработки: для печатного и рукописного текста
        # Пробуем режим для РУКОПИСНОГО текста (более агрессивная обработка)
        try:
            print("[INFO] Using handwriting-optimized preprocessing")
            binary = self.enhance_for_handwriting(enhanced)
        except Exception as e:
            print(f"[WARNING] Handwriting preprocessing failed, using standard: {e}")
            # Fallback на стандартную обработку
            denoised = self.denoise(enhanced)
            binary = self.binarize(denoised)

        # Сохранение для отладки
        if save_debug:
            debug_path = image_path.replace('.jpg', '_processed.jpg')
            cv2.imwrite(debug_path, binary)
            print(f"[DEBUG] Processed image saved to {debug_path}")

        return binary


# Удобная функция для быстрого использования
def preprocess_journal_photo(image_path: str) -> np.ndarray:
    """
    Предобработка фото журнала
    Возвращает обработанное изображение готовое для OCR
    """
    processor = ImageProcessor()
    return processor.preprocess_for_ocr(image_path)
