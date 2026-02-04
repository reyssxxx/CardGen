"""
Детекция ячеек таблицы с оценками
Использует морфологические операции для поиска линий сетки
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional


class GradeCellDetector:
    """
    Находит ячейки таблицы с оценками на изображении журнала
    """

    def __init__(self, debug: bool = False):
        """
        Args:
            debug: Если True, сохраняет промежуточные изображения для отладки
        """
        self.debug = debug
        self.min_cell_width = 30  # Минимальная ширина ячейки в пикселях
        self.min_cell_height = 25  # Минимальная высота ячейки в пикселях
        self.line_merge_tolerance = 10  # Толерантность для объединения близких линий

    def detect_cells(self, image: np.ndarray, names_region_width: float = 0.30) -> List[Dict]:
        """
        Детектирует все ячейки с оценками на изображении

        Args:
            image: Изображение журнала
            names_region_width: Ширина области с именами (будет пропущена)

        Returns:
            Список словарей с информацией о ячейках:
            [{'bbox': (x, y, w, h), 'row': int, 'col': int, 'center_y': int}]
        """
        print("[INFO] Starting cell detection...")

        # Пропускаем левую часть с именами, обрабатываем только зону с оценками
        height, width = image.shape[:2]
        x_start = int(width * names_region_width)
        grades_region = image[:, x_start:]

        # Конвертируем в grayscale
        if len(grades_region.shape) == 3:
            gray = cv2.cvtColor(grades_region, cv2.COLOR_BGR2GRAY)
        else:
            gray = grades_region.copy()

        if self.debug:
            cv2.imwrite('debug_cell_00_original_grades_region.jpg', grades_region)

        # Предобработка для детекции линий
        preprocessed = self._preprocess_for_lines(gray)

        if self.debug:
            cv2.imwrite('debug_cell_01_preprocessed.jpg', preprocessed)

        # Детектируем горизонтальные линии
        h_lines_coords = self._detect_horizontal_lines(preprocessed)
        print(f"[INFO] Detected {len(h_lines_coords)} horizontal lines")

        # Детектируем вертикальные линии
        v_lines_coords = self._detect_vertical_lines(preprocessed)
        print(f"[INFO] Detected {len(v_lines_coords)} vertical lines")

        if len(h_lines_coords) < 2 or len(v_lines_coords) < 2:
            print("[WARNING] Not enough lines detected for grid")
            return []

        # Создаем сетку ячеек из пересечений линий
        cells = self._create_cell_grid(h_lines_coords, v_lines_coords, x_start)

        # Фильтруем ячейки по размеру
        valid_cells = []
        for cell in cells:
            x, y, w, h = cell['bbox']
            if w >= self.min_cell_width and h >= self.min_cell_height:
                valid_cells.append(cell)

        print(f"[INFO] Found {len(valid_cells)} valid cells")

        # Debug: визуализация детектированных ячеек
        if self.debug and valid_cells:
            self._visualize_cells(image, valid_cells)

        return valid_cells

    def _preprocess_for_lines(self, gray: np.ndarray) -> np.ndarray:
        """
        Предобработка изображения для детекции линий таблицы
        """
        # Легкий деноизинг (сохраняем края)
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10)

        # Adaptive threshold для бинаризации
        # BINARY_INV чтобы линии были белыми на черном фоне
        binary = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=15,
            C=2
        )

        return binary

    def _detect_horizontal_lines(self, binary: np.ndarray) -> List[int]:
        """
        Детектирует горизонтальные линии таблицы

        Returns:
            Список Y-координат горизонтальных линий (отсортированный)
        """
        # Создаем горизонтальный kernel (широкий и короткий)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1))

        # Морфологическая операция OPEN для выделения горизонтальных линий
        horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)

        if self.debug:
            cv2.imwrite('debug_cell_02_horizontal_lines.jpg', horizontal_lines)

        # Находим контуры горизонтальных линий
        contours, _ = cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Извлекаем Y-координаты
        y_coords = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Фильтруем слишком короткие линии
            if w > binary.shape[1] * 0.3:  # Хотя бы 30% ширины
                y_coords.append(y)

        # Сортируем и объединяем близкие координаты
        y_coords = sorted(set(y_coords))
        merged_coords = self._merge_close_coords(y_coords, self.line_merge_tolerance)

        return merged_coords

    def _detect_vertical_lines(self, binary: np.ndarray) -> List[int]:
        """
        Детектирует вертикальные линии таблицы

        Returns:
            Список X-координат вертикальных линий (отсортированный)
        """
        # Создаем вертикальный kernel (узкий и высокий)
        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 30))

        # Морфологическая операция OPEN для выделения вертикальных линий
        vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)

        if self.debug:
            cv2.imwrite('debug_cell_03_vertical_lines.jpg', vertical_lines)

        # Находим контуры вертикальных линий
        contours, _ = cv2.findContours(vertical_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Извлекаем X-координаты
        x_coords = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            # Фильтруем слишком короткие линии
            if h > binary.shape[0] * 0.2:  # Хотя бы 20% высоты
                x_coords.append(x)

        # Сортируем и объединяем близкие координаты
        x_coords = sorted(set(x_coords))
        merged_coords = self._merge_close_coords(x_coords, self.line_merge_tolerance)

        return merged_coords

    def _merge_close_coords(self, coords: List[int], tolerance: int) -> List[int]:
        """
        Объединяет близкие координаты (убирает дубликаты линий)

        Args:
            coords: Список координат (отсортированный)
            tolerance: Максимальное расстояние для объединения

        Returns:
            Список уникальных координат
        """
        if not coords:
            return []

        merged = [coords[0]]

        for coord in coords[1:]:
            if coord - merged[-1] > tolerance:
                merged.append(coord)
            # Если координаты близко - пропускаем (уже есть в merged)

        return merged

    def _create_cell_grid(self, h_lines: List[int], v_lines: List[int], x_offset: int) -> List[Dict]:
        """
        Создает сетку ячеек из пересечений горизонтальных и вертикальных линий

        Args:
            h_lines: Y-координаты горизонтальных линий
            v_lines: X-координаты вертикальных линий
            x_offset: Смещение по X (левая часть с именами была обрезана)

        Returns:
            Список ячеек с их координатами
        """
        cells = []

        # Создаем ячейки из пересечений линий
        for row_idx in range(len(h_lines) - 1):
            for col_idx in range(len(v_lines) - 1):
                # Координаты ячейки
                x1 = v_lines[col_idx]
                x2 = v_lines[col_idx + 1]
                y1 = h_lines[row_idx]
                y2 = h_lines[row_idx + 1]

                # Размеры ячейки
                w = x2 - x1
                h = y2 - y1

                # Центр ячейки по Y (для привязки к студентам)
                center_y = y1 + h // 2

                cell = {
                    'bbox': (x1 + x_offset, y1, w, h),  # Добавляем x_offset обратно
                    'row': row_idx,
                    'col': col_idx,
                    'center_y': center_y
                }

                cells.append(cell)

        return cells

    def _visualize_cells(self, original_image: np.ndarray, cells: List[Dict]) -> None:
        """
        Визуализирует детектированные ячейки для отладки
        """
        vis = original_image.copy()

        # Рисуем каждую ячейку
        for cell in cells:
            x, y, w, h = cell['bbox']
            row, col = cell['row'], cell['col']

            # Рисуем прямоугольник
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Подписываем номер строки и столбца
            label = f"R{row}C{col}"
            cv2.putText(vis, label, (x + 5, y + 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, (255, 0, 0), 1)

        cv2.imwrite('debug_cell_04_final_cells.jpg', vis)
        print("[DEBUG] Saved visualization: debug_cell_04_final_cells.jpg")
