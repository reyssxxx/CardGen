"""
Детекция и выравнивание документов/таблиц
Находит границы документа и исправляет перспективу
"""

import cv2
import numpy as np
from typing import Optional, Tuple


class DocumentScanner:
    """
    Находит границы документа на фото и исправляет перспективу
    Полезно для фото журналов/документов сделанных под углом
    """

    def __init__(self):
        pass

    def order_points(self, pts):
        """
        Упорядочить точки в порядке: top-left, top-right, bottom-right, bottom-left
        """
        rect = np.zeros((4, 2), dtype="float32")

        # Сумма координат: top-left будет иметь наименьшую сумму, bottom-right наибольшую
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        # Разница координат: top-right будет иметь наименьшую разницу, bottom-left наибольшую
        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]

        return rect

    def four_point_transform(self, image, pts):
        """
        Применить перспективное преобразование для выравнивания документа
        """
        rect = self.order_points(pts)
        (tl, tr, br, bl) = rect

        # Вычислить ширину нового изображения
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))

        # Вычислить высоту нового изображения
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))

        # Целевые точки для перспективного преобразования
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]], dtype="float32")

        # Вычислить матрицу перспективного преобразования и применить
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))

        return warped

    def find_document_contour(self, image: np.ndarray) -> Optional[np.ndarray]:
        """
        Найти контур документа на изображении

        Returns:
            Массив из 4 точек углов документа, или None если не найдено
        """
        # Конвертируем в grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Размытие для уменьшения шума
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Детекция границ с помощью Canny
        # Используем auto thresholding
        median = np.median(blurred)
        lower = int(max(0, 0.7 * median))
        upper = int(min(255, 1.3 * median))
        edged = cv2.Canny(blurred, lower, upper)

        # Морфологическое закрытие для соединения разрывов
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel)

        # Найти контуры
        contours, _ = cv2.findContours(closed.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return None

        # Сортировать контуры по площади (самый большой первый)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        # Найти первый контур с 4 углами (прямоугольник)
        for contour in contours[:10]:  # Проверяем топ 10
            # Аппроксимировать контур
            peri = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, 0.02 * peri, True)

            # Если контур имеет 4 точки, это наш документ
            if len(approx) == 4:
                # Проверяем что площадь достаточно большая
                area = cv2.contourArea(approx)
                image_area = image.shape[0] * image.shape[1]

                if area > image_area * 0.3:  # Хотя бы 30% изображения
                    return approx.reshape(4, 2)

        return None

    def scan_document(self, image: np.ndarray) -> Tuple[Optional[np.ndarray], bool]:
        """
        Найти и выровнять документ на изображении

        Returns:
            (выровненное_изображение, успешно)
        """
        # Найти контур документа
        contour = self.find_document_contour(image)

        if contour is None:
            print("[INFO] Document contour not found, using original image")
            return image, False

        print("[INFO] Document contour found, applying perspective correction")

        # Применить перспективное преобразование
        warped = self.four_point_transform(image, contour)

        return warped, True

    def scan_and_enhance(self, image: np.ndarray) -> np.ndarray:
        """
        Найти документ, выровнять и улучшить для OCR

        Returns:
            Обработанное изображение (grayscale)
        """
        # Сканирование документа
        scanned, found = self.scan_document(image)

        # Конвертация в grayscale
        if len(scanned.shape) == 3:
            gray = cv2.cvtColor(scanned, cv2.COLOR_BGR2GRAY)
        else:
            gray = scanned

        # Улучшение контраста
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        return enhanced
