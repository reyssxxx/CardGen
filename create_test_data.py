"""
Скрипт для создания тестовых данных
"""
from datetime import datetime, timedelta
import random
from database.user_repository import UserRepository
from database.grade_repository import GradeRepository

def create_test_data():
    """Создает тестовые данные для проверки функционала"""
    print("[INFO] Creating test data...")

    user_repo = UserRepository()
    grade_repo = GradeRepository()

    # Используем реального ученика из БД
    students = user_repo.get_all_students()

    if not students:
        print("[ERROR] No students found in database!")
        return

    test_student_id, test_student_name = students[0]
    test_class = "11Т"  # Класс по умолчанию

    # Зарегистрировать тестового ученика
    print(f"[INFO] Registering test student: {test_student_name}")
    try:
        user_repo.register_user(test_student_name, test_student_id, is_teacher=False)
        print("[SUCCESS] Student registered")
    except Exception as e:
        print(f"[INFO] Student already exists: {e}")

    # Предметы
    subjects = [
        "Математика",
        "Русский язык",
        "Литература",
        "Физика",
        "Химия",
        "Информатика",
        "История",
        "Обществознание"
    ]

    # Создать тестовые оценки за последние 14 дней
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=14)

    print(f"[INFO] Creating grades for period: {start_date} - {end_date}")

    # Генерация дат (каждые 2 дня)
    current_date = start_date
    test_grades = []

    while current_date <= end_date:
        # Для каждой даты добавить оценки по случайным предметам
        num_subjects = random.randint(2, 5)
        selected_subjects = random.sample(subjects, num_subjects)

        for subject in selected_subjects:
            grade = random.choice(['5', '5', '4', '4', '4', '3'])  # Больше хороших оценок
            test_grades.append({
                'student_name': test_student_name,
                'class': test_class,
                'subject': subject,
                'grade': grade,
                'date': current_date.strftime('%Y-%m-%d'),
                'teacher_username': 'test_teacher'
            })

        current_date += timedelta(days=2)

    print(f"[INFO] Adding {len(test_grades)} test grades...")

    try:
        count = grade_repo.add_grades_bulk(test_grades)
        print(f"[SUCCESS] Added {count} grades")
    except Exception as e:
        print(f"[ERROR] Failed to add grades: {e}")
        import traceback
        traceback.print_exc()

    print("[SUCCESS] Test data created successfully!")
    print(f"\nTest student: {test_student_name}")
    print(f"Telegram ID: {test_student_id}")
    print(f"Class: {test_class}")
    print(f"Grades count: {len(test_grades)}")


if __name__ == "__main__":
    create_test_data()
