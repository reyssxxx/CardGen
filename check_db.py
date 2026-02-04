"""
Скрипт для проверки и очистки БД
"""
import sqlite3

# Подключение к БД
conn = sqlite3.connect('data/database.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=" * 60)
print("ТАБЛИЦА Users:")
print("=" * 60)

try:
    cur.execute('SELECT * FROM Users')
    users = cur.fetchall()

    if users:
        print(f"\nНайдено пользователей: {len(users)}\n")
        print(f"{'ID':<15} {'ФИ':<30} {'isTeacher':<10}")
        print("-" * 60)

        for row in users:
            print(f"{row['ID']:<15} {row['ФИ']:<30} {row['isTeacher']:<10}")
    else:
        print("\nТаблица Users пустая")

except Exception as e:
    print(f"Ошибка: {e}")

print("\n" + "=" * 60)
print("ТАБЛИЦА Grades:")
print("=" * 60)

try:
    cur.execute('SELECT COUNT(*) as count FROM Grades')
    count = cur.fetchone()['count']
    print(f"\nВсего оценок: {count}")

    if count > 0:
        cur.execute('SELECT student_name, COUNT(*) as grades_count FROM Grades GROUP BY student_name')
        for row in cur.fetchall():
            print(f"  {row['student_name']}: {row['grades_count']} оценок")

except Exception as e:
    print(f"Ошибка: {e}")

conn.close()

print("\n" + "=" * 60)
print("\nДля очистки БД запустите: python clear_db.py")
