"""
Тест детекции ячеек таблицы на реальных фото
"""
import cv2
import sys
from pathlib import Path

# Прямой импорт без services/__init__.py
sys.path.insert(0, 'services')
from grade_cell_detector import GradeCellDetector
from document_scanner import DocumentScanner

# Тестовые изображения
test_images = [
    'data/uploaded_photos/reysstema_20260204_124140.jpg',
    'data/uploaded_photos/reysstema_20260204_124544.jpg',
    'data/uploaded_photos/reysstema_20260204_125717.jpg',
    'data/uploaded_photos/reysstema_20260204_130948.jpg',
]

print("=" * 70)
print("ТЕСТ ДЕТЕКЦИИ ЯЧЕЕК ТАБЛИЦЫ")
print("=" * 70)
print()

# Инициализация
scanner = DocumentScanner()
detector = GradeCellDetector(debug=True)

total_cells = 0
total_images = 0

for img_path in test_images:
    if not Path(img_path).exists():
        print(f"⚠ Файл не найден: {img_path}")
        continue

    print(f"\n{'='*70}")
    print(f"Тестирование: {img_path}")
    print(f"{'='*70}")

    # Загрузить изображение
    image = cv2.imread(img_path)
    if image is None:
        print(f"✗ Не удалось загрузить изображение")
        continue

    print(f"✓ Изображение загружено: {image.shape}")

    # Сканирование документа (исправление перспективы)
    scanned, found = scanner.scan_document(image)
    if found:
        print("✓ Документ отсканирован, перспектива исправлена")
        image = scanned
    else:
        print("⚠ Документ не найден, используем оригинал")

    # Детекция ячеек
    cells = detector.detect_cells(image, names_region_width=0.30)

    if cells:
        print(f"\n✓ Найдено ячеек: {len(cells)}")

        # Статистика по строкам и столбцам
        rows = set(c['row'] for c in cells)
        cols = set(c['col'] for c in cells)

        print(f"  - Строк: {len(rows)}")
        print(f"  - Столбцов: {len(cols)}")

        # Показать первые 5 ячеек как пример
        print(f"\n  Примеры ячеек:")
        for i, cell in enumerate(cells[:5]):
            x, y, w, h = cell['bbox']
            print(f"    {i+1}. Row {cell['row']}, Col {cell['col']}: "
                  f"bbox=({x},{y},{w},{h}), center_y={cell['center_y']}")

        total_cells += len(cells)
        total_images += 1

        print(f"\n  Debug изображения сохранены в текущей директории")
    else:
        print("✗ Ячейки не найдены!")

print()
print("=" * 70)
print("ИТОГИ")
print("=" * 70)
print(f"Обработано изображений: {total_images}")
print(f"Всего ячеек детектировано: {total_cells}")
if total_images > 0:
    print(f"Среднее кол-во ячеек на изображение: {total_cells / total_images:.1f}")
print()

if total_cells > 0:
    print("✓ Детекция ячеек работает!")
    print("\nПроверьте debug изображения:")
    print("  - debug_cell_00_original_grades_region.jpg - область с оценками")
    print("  - debug_cell_01_preprocessed.jpg - бинаризованное изображение")
    print("  - debug_cell_02_horizontal_lines.jpg - горизонтальные линии")
    print("  - debug_cell_03_vertical_lines.jpg - вертикальные линии")
    print("  - debug_cell_04_final_cells.jpg - финальные ячейки")
else:
    print("✗ Детекция не работает, нужна отладка")
    print("\nВозможные причины:")
    print("  1. Слишком мало линий детектировано")
    print("  2. Линии недостаточно длинные")
    print("  3. Нужно настроить параметры kernel")

print()
print("=" * 70)
