"""
Тест полного OCR pipeline на реальном изображении
С базой студентов и fuzzy matching
"""
import cv2
from services.ocr_service import JournalOCR

# Загрузить изображение
image_path = 'data/uploaded_photos/reysstema_20260203_234518.jpg'
image = cv2.imread(image_path)

print("=" * 70)
print("FULL OCR PIPELINE TEST WITH FUZZY MATCHING")
print("=" * 70)
print(f"\nImage: {image_path}")
print(f"Shape: {image.shape}")
print()

# База студентов из журнала
students_list = [
    "Агнушевич Марк",
    "Бабичев Артем",
    "Богацкий Максим",
    "Горохов-Абубекиров Арсений",
    "Ефимов Александр",
    "Жданов Эдуард",
    "Клепалов Мирослав",
    "Колесник Владимир",
    "Костин Роман",
    "Кривоносов Никита",
    "Кузьмин Роман",
    "Лаптев Игорь",
    "Мажара Станислав",
    "Микула Анна",
    "Недайводина Ева",
    "Панасова Злата",
    "Полдубняк Михаил",
    "Ранов Владимир",
    "Синдикаева Джамиля",
    "Соколов Илья",
    "Сутягина Вероника",
    "Турикин Илья",
    "Штука Илья"
]

print(f"Expected students: {len(students_list)}")
print()

# Инициализировать OCR
print("Initializing OCR...")
ocr = JournalOCR(use_tesseract_for_names=True)

# Извлечь имена
print("\nExtracting names with Tesseract...")
detected_names = ocr.extract_student_names(image)

print(f"\nDetected: {len(detected_names)} names")
print()

# Применить fuzzy matching
print("Applying fuzzy matching with rapidfuzz...")
print("-" * 70)

matched_names = ocr._match_names(detected_names, students_list)

print()
print("=" * 70)
print("RESULTS")
print("=" * 70)

correct_matches = 0
for detected, matched in zip(detected_names, matched_names):
    is_correct = matched in students_list
    status = "✓" if is_correct else "✗"

    if is_correct:
        correct_matches += 1

    # Показываем только если было исправление
    if detected != matched:
        print(f"{status} '{detected}' → '{matched}'")

print()
print(f"Accuracy: {correct_matches}/{len(matched_names)} = {correct_matches/len(matched_names)*100:.1f}%")
print()

# Детальная статистика
print("=" * 70)
print("STATISTICS")
print("=" * 70)
print(f"Expected students:  {len(students_list)}")
print(f"Detected names:     {len(detected_names)}")
print(f"Correctly matched:  {correct_matches}")
print(f"Match rate:         {correct_matches/len(students_list)*100:.1f}%")
print()

# Показать не найденных
matched_set = set(matched_names)
expected_set = set(students_list)
missing = expected_set - matched_set

if missing:
    print(f"Missing students ({len(missing)}):")
    for name in sorted(missing):
        print(f"  - {name}")
else:
    print("✓ All students found!")

print()
print("=" * 70)
