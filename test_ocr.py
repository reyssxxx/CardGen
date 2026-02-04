"""
Тестовый скрипт для проверки OCR пайплайна
Использовать: python test_ocr.py <путь_к_фото_журнала>
"""
import sys
from pathlib import Path

# Импорт из нашего проекта
from services.ocr_pipeline import process_journal_photo
from utils.config_loader import get_students_by_class


def test_ocr_pipeline(image_path: str):
    """
    Тест полного пайплайна OCR
    """
    print("=" * 70)
    print("TEST OCR PIPELINE")
    print("=" * 70)

    # Проверка файла
    if not Path(image_path).exists():
        print(f"[ERROR] File not found: {image_path}")
        return

    print(f"\n[INFO] Testing with image: {image_path}")

    # Тестовые данные
    subject = "Математика"
    teacher_username = "test_teacher"
    expected_class = "11Т"  # Если знаете класс заранее

    # Загрузка списка учеников для валидации (если есть)
    try:
        students_list = get_students_by_class(expected_class)
        print(f"[INFO] Loaded {len(students_list)} students from config")
    except Exception as e:
        print(f"[WARNING] Could not load students: {e}")
        students_list = None

    # Запуск пайплайна
    print("\n" + "-" * 70)
    print("STARTING OCR PROCESSING...")
    print("-" * 70 + "\n")

    result = process_journal_photo(
        image_path=image_path,
        subject=subject,
        teacher_username=teacher_username,
        students_list=students_list,
        expected_class=expected_class,
        save_debug=True  # Сохранить промежуточные изображения
    )

    # Вывод результатов
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    success = result.get('success', False)
    print(f"\nSuccess: {success}")

    if not success:
        print(f"Error: {result.get('error', 'Unknown error')}")
        print(f"Warnings: {result.get('warnings', [])}")
        return

    # OCR результаты
    ocr_result = result.get('ocr_result', {})
    db_data = result.get('db_data', {})
    warnings = result.get('warnings', [])

    print(f"\nDetected Class: {ocr_result.get('class')}")
    print(f"Detected Dates: {len(ocr_result.get('dates', []))} dates")

    dates = ocr_result.get('dates', [])
    if dates:
        print(f"  Dates: {', '.join(dates[:5])}" + (" ..." if len(dates) > 5 else ""))

    print(f"\nDetected Students: {len(ocr_result.get('students', []))} students")

    students = ocr_result.get('students', [])
    if students:
        print("\nFirst 3 students:")
        for i, student_data in enumerate(students[:3], 1):
            name = student_data['name']
            grades = student_data.get('grades_row', [])
            grades_str = ', '.join([str(g) if g else '-' for g in grades[:5]])
            print(f"  {i}. {name}: {grades_str}" + (" ..." if len(grades) > 5 else ""))

    # Данные для БД
    if db_data:
        grades_data = db_data.get('grades_data', [])
        print(f"\nGrades ready for database: {len(grades_data)} entries")

        if grades_data:
            print("\nFirst 5 grade entries:")
            for i, grade_entry in enumerate(grades_data[:5], 1):
                print(f"  {i}. {grade_entry['student_name']}: "
                      f"{grade_entry['grade']} on {grade_entry['date']}")

    # Warnings
    if warnings:
        print(f"\n[WARNINGS] {len(warnings)} warnings:")
        for warning in warnings:
            print(f"  - {warning}")

    # Debug info
    debug_info = ocr_result.get('debug_info', {})
    if debug_info:
        print("\n[DEBUG INFO]")
        for key, value in debug_info.items():
            print(f"  {key}: {value}")

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_ocr.py <path_to_journal_photo>")
        print("\nExample:")
        print("  python test_ocr.py data/uploaded_photos/journal_test.jpg")
        sys.exit(1)

    image_path = sys.argv[1]
    test_ocr_pipeline(image_path)
