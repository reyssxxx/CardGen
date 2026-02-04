"""
Скрипт для проверки работоспособности всех команд бота
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import asyncio
from database.user_repository import UserRepository
from database.grade_repository import GradeRepository
from grade_utils import generate_grade
from utils.formatters import format_student_grades_report, format_statistics, calculate_average
from datetime import datetime, timedelta

def test_database():
    """Проверка подключения к БД и наличия данных"""
    print("\n" + "="*60)
    print("📊 ТЕСТ 1: Проверка базы данных")
    print("="*60)

    user_repo = UserRepository()
    grade_repo = GradeRepository()

    # Проверка пользователей
    students = user_repo.get_all_students()
    teachers = user_repo.get_all_teachers()

    print(f"✅ Учеников в БД: {len(students)}")
    print(f"✅ Учителей в БД: {len(teachers)}")

    if students:
        print("\n👥 Ученики:")
        for user_id, name in students[:5]:  # Показать первых 5
            print(f"  - {name} (ID: {user_id})")

    if teachers:
        print("\n👨‍🏫 Учителя:")
        for user_id, name in teachers[:5]:
            print(f"  - {name} (ID: {user_id})")

    # Проверка оценок
    if students:
        test_student_id, test_student_name = students[0]
        grades = grade_repo.get_student_grades(test_student_name)
        print(f"\n📚 Оценок у {test_student_name}: {len(grades)}")

        if grades:
            print(f"  Последняя оценка: {grades[-1]['subject']} - {grades[-1]['grade']} ({grades[-1]['date']})")
            return test_student_id, test_student_name

    return None, None


def test_grade_generation(student_id, student_name):
    """Проверка генерации табеля"""
    print("\n" + "="*60)
    print("🎴 ТЕСТ 2: Генерация табеля")
    print("="*60)

    try:
        output_file = f"data/grade_cards/test_{student_name.replace(' ', '_')}.png"
        print(f"🔄 Генерирую табель для {student_name}...")

        card_path = generate_grade(telegram_id=student_id, output_file=output_file)

        print(f"✅ Табель успешно сгенерирован: {card_path}")
        return True
    except Exception as e:
        print(f"❌ Ошибка генерации табеля: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_grades_report(student_name):
    """Проверка команды /grades"""
    print("\n" + "="*60)
    print("📝 ТЕСТ 3: Команда /grades (текстовый отчет)")
    print("="*60)

    grade_repo = GradeRepository()

    # Получить оценки за 90 дней
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    grades = grade_repo.get_student_grades(
        student_name=student_name,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )

    if not grades:
        print("⚠️  Нет оценок за последние 90 дней")
        return False

    # Сгруппировать по предметам
    grades_by_subject = {}
    for grade in grades:
        subject = grade['subject']
        if subject not in grades_by_subject:
            grades_by_subject[subject] = []
        grades_by_subject[subject].append(grade['grade'])

    # Форматировать отчет
    report = format_student_grades_report(student_name, grades_by_subject)
    print(report)
    print("\n✅ Команда /grades работает корректно")
    return True


def test_statistics(student_name):
    """Проверка команды /stats"""
    print("\n" + "="*60)
    print("📈 ТЕСТ 4: Команда /stats (статистика)")
    print("="*60)

    grade_repo = GradeRepository()

    # Получить оценки за 90 дней
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=90)

    grades = grade_repo.get_student_grades(
        student_name=student_name,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d')
    )

    if not grades:
        print("⚠️  Нет оценок за последние 90 дней")
        return False

    # Собрать статистику
    grade_counts = {'5': 0, '4': 0, '3': 0, '2': 0}
    grades_by_subject = {}

    for grade in grades:
        if grade['grade'] in grade_counts:
            grade_counts[grade['grade']] += 1

        subject = grade['subject']
        if subject not in grades_by_subject:
            grades_by_subject[subject] = []
        if grade['grade'] in ['2', '3', '4', '5']:
            grades_by_subject[subject].append(grade['grade'])

    # Средний балл
    avg = grade_repo.get_average_grade(student_name)

    # Топ-3 предмета
    subject_averages = {}
    for subject, subject_grades in grades_by_subject.items():
        if subject_grades:
            subject_averages[subject] = calculate_average(subject_grades)

    sorted_subjects = sorted(subject_averages.items(), key=lambda x: x[1], reverse=True)
    top_3 = sorted_subjects[:3]

    # Вывод статистики
    stats = {
        'grade_counts': grade_counts,
        'average_grade': round(avg, 2) if avg else 0,
        'total_grades': len(grades)
    }

    report = format_statistics(stats)
    print(report)

    if top_3:
        print("\n🏆 Лучшие предметы:")
        for i, (subject, avg_grade) in enumerate(top_3, 1):
            print(f"{i}. {subject} ({avg_grade:.2f})")

    print("\n✅ Команда /stats работает корректно")
    return True


def test_config_files():
    """Проверка конфигурационных файлов"""
    print("\n" + "="*60)
    print("⚙️  ТЕСТ 5: Проверка конфигурации")
    print("="*60)

    import json
    from pathlib import Path

    # Проверка config.json
    config_path = Path('data/config.json')
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        print(f"✅ config.json: {len(config.get('subjects', []))} предметов, {len(config.get('teachers', []))} учителей")
    else:
        print("❌ config.json не найден")
        return False

    # Проверка students.json
    students_path = Path('data/students.json')
    if students_path.exists():
        with open(students_path, 'r', encoding='utf-8') as f:
            students = json.load(f)
        total_students = sum(len(v) for v in students.values())
        print(f"✅ students.json: {total_students} учеников в {len(students)} классах")
    else:
        print("❌ students.json не найден")
        return False

    return True


def main():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("🧪 ТЕСТИРОВАНИЕ ФУНКЦИОНАЛА БОТА")
    print("="*60)

    results = []

    # Тест 1: База данных
    student_id, student_name = test_database()
    results.append(("База данных", student_id is not None))

    if not student_id:
        print("\n❌ Нет данных для тестирования. Запустите create_test_data.py")
        return

    # Тест 2: Генерация табеля
    success = test_grade_generation(student_id, student_name)
    results.append(("Генерация табеля (/getcard)", success))

    # Тест 3: Текстовый отчет
    success = test_grades_report(student_name)
    results.append(("Команда /grades", success))

    # Тест 4: Статистика
    success = test_statistics(student_name)
    results.append(("Команда /stats", success))

    # Тест 5: Конфигурация
    success = test_config_files()
    results.append(("Конфигурационные файлы", success))

    # Итоги
    print("\n" + "="*60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)

    for name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {name}")

    passed = sum(1 for _, success in results if success)
    total = len(results)

    print(f"\n🎯 Пройдено тестов: {passed}/{total}")

    if passed == total:
        print("\n🎉 Все тесты пройдены успешно!")
        print("\n📝 Следующие шаги:")
        print("   1. Запустите бота: python main.py")
        print("   2. Протестируйте команды в Telegram:")
        print("      - /start - регистрация")
        print("      - /help - справка")
        print("      - /getcard - табель (для ученика)")
        print("      - /photo - загрузка журнала (для учителя)")
    else:
        print("\n⚠️  Некоторые тесты не прошли. Проверьте ошибки выше.")


if __name__ == "__main__":
    main()
