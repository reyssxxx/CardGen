"""
Скрипт для удаления пользователя из БД
"""
import sqlite3
import sys

if len(sys.argv) < 2:
    print("Usage: python delete_user.py <user_id>")
    print("\nНапример: python delete_user.py 1149921690")
    print("\nДля удаления всех пользователей: python delete_user.py ALL")
    sys.exit(1)

user_id_input = sys.argv[1]

# Подключение к БД
conn = sqlite3.connect('data/database.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

if user_id_input.upper() == "ALL":
    # Удалить всех пользователей
    print("Удаление ВСЕХ пользователей...")

    cur.execute('SELECT COUNT(*) as count FROM Users')
    count = cur.fetchone()['count']

    if count == 0:
        print("Таблица Users уже пустая")
    else:
        # Удалить оценки всех пользователей
        cur.execute('DELETE FROM Grades')
        grades_deleted = cur.rowcount

        # Удалить всех пользователей
        cur.execute('DELETE FROM Users')
        users_deleted = cur.rowcount

        conn.commit()

        print(f"✅ Удалено пользователей: {users_deleted}")
        print(f"✅ Удалено оценок: {grades_deleted}")

else:
    # Удалить конкретного пользователя
    try:
        user_id = int(user_id_input)
    except ValueError:
        print(f"❌ Ошибка: '{user_id_input}' не является числом")
        sys.exit(1)

    # Проверить существует ли пользователь
    cur.execute('SELECT * FROM Users WHERE ID=?', (user_id,))
    user = cur.fetchone()

    if not user:
        print(f"❌ Пользователь с ID {user_id} не найден")
        sys.exit(1)

    print(f"Найден пользователь:")
    print(f"  ID: {user['ID']}")
    print(f"  ФИ: {user['ФИ']}")
    print(f"  isTeacher: {user['isTeacher']}")

    # ВАЖНО: Сначала удалить оценки (из-за FOREIGN KEY)
    cur.execute('DELETE FROM Grades WHERE student_name=?', (user['ФИ'],))
    grades_deleted = cur.rowcount
    print(f"  Удалено оценок: {grades_deleted}")

    # Потом удалить пользователя
    cur.execute('DELETE FROM Users WHERE ID=?', (user_id,))
    users_deleted = cur.rowcount

    conn.commit()

    print(f"\n✅ Удален пользователь: {user['ФИ']} (ID: {user_id})")
    if grades_deleted > 0:
        print(f"✅ Удалено оценок: {grades_deleted}")

conn.close()

print("\n✅ Готово! Запустите python check_db.py для проверки")
