"""
Тестовый скрипт для проверки генерации табелей
"""
from datetime import datetime, timedelta
from services.grade_generator import GradeCardGenerator
from database.grade_repository import GradeRepository

def test_grade_generator():
    """Тестирует генерацию табеля"""
    print("[TEST] Starting grade generator test...")

    # Инициализация
    generator = GradeCardGenerator()
    grade_repo = GradeRepository()

    # Получить список учеников из БД
    from database.user_repository import UserRepository
    user_repo = UserRepository()
    students = user_repo.get_all_students()

    if not students:
        print("[ERROR] No students found in database")
        return

    # Взять первого ученика
    student_id, student_name = students[0]
    print(f"[TEST] Testing with student: {student_name} (ID: {student_id})")

    # Получить оценки ученика
    grades = grade_repo.get_student_grades(student_name)

    if not grades:
        print(f"[ERROR] No grades found for {student_name}")
        return

    print(f"[TEST] Found {len(grades)} grades for {student_name}")

    # Определить класс
    class_name = grades[0]['class']
    print(f"[TEST] Class: {class_name}")

    # Генерировать табель за последние 14 дней
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=14)

    print(f"[TEST] Period: {start_date} - {end_date}")

    try:
        card_path = generator.generate_card(
            student_name=student_name,
            class_name=class_name,
            period_start=start_date,
            period_end=end_date
        )

        print(f"[SUCCESS] Grade card generated: {card_path}")
        print("[TEST] Opening image...")

        # Открыть изображение
        from PIL import Image
        img = Image.open(card_path)
        img.show()

        print("[SUCCESS] Test completed!")

    except Exception as e:
        print(f"[ERROR] Failed to generate card: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_grade_generator()
