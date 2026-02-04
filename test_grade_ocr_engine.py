"""
Тест OCR оценок из ячеек
Тестирует на первых 50 ячейках из одного реального изображения
"""
import cv2
import sys

# Прямой импорт
sys.path.insert(0, 'services')
from grade_cell_detector import GradeCellDetector
from grade_ocr import GradeOCREngine
from document_scanner import DocumentScanner

# Тестовое изображение
test_image = 'data/uploaded_photos/reysstema_20260204_124140.jpg'

print("=" * 70)
print("ТЕСТ OCR ОЦЕНОК ИЗ ЯЧЕЕК")
print("=" * 70)
print(f"\nИзображение: {test_image}")
print()

# Загрузить изображение
image = cv2.imread(test_image)
if image is None:
    print(f"✗ Не удалось загрузить изображение")
    sys.exit(1)

print(f"✓ Изображение загружено: {image.shape}")

# Сканирование документа
scanner = DocumentScanner()
scanned, found = scanner.scan_document(image)
if found:
    print("✓ Документ отсканирован")
    image = scanned

# Детекция ячеек
detector = GradeCellDetector(debug=False)
cells = detector.detect_cells(image, names_region_width=0.30)

if not cells:
    print("✗ Ячейки не найдены!")
    sys.exit(1)

print(f"✓ Найдено ячеек: {len(cells)}")
print()

# Инициализация OCR движка
ocr_engine = GradeOCREngine(debug=True)

# Пропускаем первые 2 строки (заголовки), тестируем строки 3-8 (6 строк × 17 столбцов = ~100 ячеек)
# Строки 0,1 = заголовки/даты
# Строки 2+ = студенты с оценками
start_row = 2
end_row = 8
test_cells = [c for c in cells if start_row <= c['row'] < end_row]

print(f"Пропускаем строки 0-{start_row-1} (заголовки)")
print(f"Тестируем строки {start_row}-{end_row-1} (студенты с оценками)")

print(f"Тестирование OCR на {len(test_cells)} ячейках...")
print("=" * 70)

results = []

for i, cell in enumerate(test_cells):
    x, y, w, h = cell['bbox']

    # Извлечь изображение ячейки
    cell_img = image[y:y+h, x:x+w]

    # Распознать оценку
    result = ocr_engine.recognize_grade(cell_img, cell)
    results.append(result)

    # Показываем результат
    status = "✓" if result['text'] else "✗"
    review = " [REVIEW]" if result.get('needs_review', False) else ""

    print(f"{i+1:2d}. R{cell['row']:2d}C{cell['col']:2d}: '{result['text']:3s}' "
          f"(conf={result['confidence']:5.1f}%, {result['method']:20s}) {status}{review}")

    # Показываем альтернативы если есть
    if result.get('alternatives'):
        print(f"     Альтернативы: {result['alternatives']}")

# Статистика
print()
print("=" * 70)
print("СТАТИСТИКА")
print("=" * 70)

recognized = [r for r in results if r['text']]
needs_review = [r for r in results if r.get('needs_review', False)]
has_consensus = [r for r in results if '+' in r.get('method', '')]

print(f"Всего ячеек протестировано:  {len(results)}")
print(f"Распознано:                   {len(recognized)} ({len(recognized)/len(results)*100:.1f}%)")
print(f"Пустых:                       {len(results) - len(recognized)}")
print()
print(f"Нужна проверка учителя:       {len(needs_review)} ({len(needs_review)/len(results)*100:.1f}%)")
print(f"С консенсусом (высокая точн.): {len(has_consensus)} ({len(has_consensus)/len(recognized)*100:.1f}% от распознанных)" if recognized else "")
print()

# Распределение оценок
grade_distribution = {}
for r in recognized:
    grade = r['text']
    grade_distribution[grade] = grade_distribution.get(grade, 0) + 1

if grade_distribution:
    print("Распределение оценок:")
    for grade in sorted(grade_distribution.keys()):
        count = grade_distribution[grade]
        print(f"  '{grade}': {count} ({count/len(recognized)*100:.1f}%)")

# Средняя уверенность
if recognized:
    avg_confidence = sum(r['confidence'] for r in recognized) / len(recognized)
    print()
    print(f"Средняя уверенность: {avg_confidence:.1f}%")

# Методы
methods = {}
for r in recognized:
    method = r['method']
    methods[method] = methods.get(method, 0) + 1

if methods:
    print()
    print("Использованные методы:")
    for method, count in sorted(methods.items(), key=lambda x: x[1], reverse=True):
        print(f"  {method}: {count}")

print()
print("=" * 70)
print("ВЫВОД")
print("=" * 70)

if len(recognized) >= len(results) * 0.3:  # Хотя бы 30% распознано
    print(f"✓ OCR работает! Распознано {len(recognized)/len(results)*100:.1f}% ячеек")

    if len(needs_review) <= len(recognized) * 0.15:  # Менее 15% требует проверки
        print(f"✓ Качество отличное! Только {len(needs_review)/len(recognized)*100:.1f}% требует проверки учителем")
    elif len(needs_review) <= len(recognized) * 0.30:
        print(f"⚠ Качество хорошее, но {len(needs_review)/len(recognized)*100:.1f}% требует проверки")
    else:
        print(f"⚠ Много случаев требуют проверки ({len(needs_review)/len(recognized)*100:.1f}%)")
else:
    print(f"✗ Распознавание работает плохо, только {len(recognized)/len(results)*100:.1f}% ячеек")
    print("\nВозможные причины:")
    print("  1. Ячейки пустые (это нормально)")
    print("  2. Handwriting too unclear")
    print("  3. Нужна настройка параметров предобработки")

print()
print("Debug изображения ячеек сохранены с префиксом debug_grade_")
print("=" * 70)
