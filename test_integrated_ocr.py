"""
Тест полного OCR pipeline с интегрированным распознаванием оценок
"""
import cv2
import sys
sys.path.insert(0, 'services')

from ocr_service import JournalOCR

# Тестовое изображение
test_image_path = 'data/uploaded_photos/reysstema_20260204_124140.jpg'

print("=" * 70)
print("ТЕСТ ПОЛНОГО OCR PIPELINE")
print("=" * 70)
print(f"\nИзображение: {test_image_path}\n")

# Загрузить изображение
image = cv2.imread(test_image_path)
if image is None:
    print(f"✗ Не удалось загрузить изображение")
    sys.exit(1)

print(f"✓ Изображение загружено: {image.shape}\n")

# Инициализировать OCR сервис
ocr = JournalOCR(use_tesseract_for_names=True)

# Обработать фото журнала
print("Запуск полного OCR pipeline...\n")
result = ocr.process_journal_photo(image)

# Показать результаты
print("\n" + "=" * 70)
print("РЕЗУЛЬТАТЫ")
print("=" * 70)

print(f"\nКласс: {result.get('class', 'не распознан')}")
print(f"Дат обнаружено: {len(result.get('dates', []))}")
print(f"Студентов обнаружено: {len(result.get('students', []))}")

print("\n" + "-" * 70)
print("СТУДЕНТЫ И ОЦЕНКИ:")
print("-" * 70)

for idx, student in enumerate(result.get('students', []), 1):
    name = student.get('name', 'Unknown')
    grades = student.get('grades_row', [])

    # Считаем непустые оценки
    non_empty = [g for g in grades if g is not None]

    print(f"{idx:2d}. {name:30s} - {len(non_empty):2d} оценок: {grades[:10]}")

print("\n" + "=" * 70)
print("ИТОГИ")
print("=" * 70)

total_students = len(result.get('students', []))
total_grades = sum(
    len([g for g in s.get('grades_row', []) if g is not None])
    for s in result.get('students', [])
)

print(f"Всего студентов: {total_students}")
print(f"Всего оценок распознано: {total_grades}")
if total_students > 0:
    print(f"Среднее оценок на студента: {total_grades / total_students:.1f}")

print("\n✓ Тест завершен!")
print("=" * 70)
