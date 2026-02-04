"""
Менеджер базы данных - создание таблиц и миграции
"""
import sqlite3
from pathlib import Path


class DatabaseManager:
    def __init__(self, db_path='./data/database.db'):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self):
        """Получить подключение к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Доступ к столбцам по имени
        return conn

    def init_database(self):
        """Инициализация всех таблиц БД"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Таблица Users (уже существует, но проверим)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Users (
                    ФИ TEXT NOT NULL,
                    ID INTEGER NOT NULL,
                    isTeacher BOOLEAN NOT NULL,
                    PRIMARY KEY (ID)
                )
            ''')

            # Таблица Grades - хранение оценок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Grades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_name TEXT NOT NULL,
                    class TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    date DATE NOT NULL,
                    teacher_username TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_name) REFERENCES Users(ФИ)
                )
            ''')

            # Индекс для быстрого поиска оценок ученика
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_grades_student
                ON Grades(student_name, date)
            ''')

            # Индекс для поиска по предмету и классу
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_grades_subject_class
                ON Grades(class, subject, date)
            ''')

            # Таблица PhotoUploads - журнал загрузок фото
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS PhotoUploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    teacher_username TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    class TEXT NOT NULL,
                    upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    file_path TEXT,
                    status TEXT DEFAULT 'pending',
                    processed_date DATETIME,
                    error_message TEXT
                )
            ''')

            # Индекс для поиска загрузок учителя
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_photo_teacher
                ON PhotoUploads(teacher_username, upload_date)
            ''')

            # Таблица ScheduledMailings - расписание рассылок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ScheduledMailings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    last_mailing_date DATE,
                    next_mailing_date DATE,
                    status TEXT DEFAULT 'active'
                )
            ''')

            # Инициализация первой записи в ScheduledMailings если её нет
            cursor.execute('SELECT COUNT(*) FROM ScheduledMailings')
            if cursor.fetchone()[0] == 0:
                cursor.execute('''
                    INSERT INTO ScheduledMailings (status) VALUES ('active')
                ''')

            conn.commit()
            print("[OK] Database initialized successfully")

        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Database initialization failed: {e}")
            raise
        finally:
            conn.close()

    def migrate_existing_data(self):
        """
        Миграция существующих данных если нужно
        (на случай если в БД уже есть данные)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Проверка наличия данных в Users
            cursor.execute('SELECT COUNT(*) FROM Users')
            user_count = cursor.fetchone()[0]

            if user_count > 0:
                print(f"[INFO] Found {user_count} users in database")

            conn.commit()

        except Exception as e:
            print(f"[WARNING] Error during migration: {e}")
        finally:
            conn.close()


# Функция для быстрого доступа
def init_db():
    """Инициализировать БД - вызывается при запуске бота"""
    db_manager = DatabaseManager()
    db_manager.init_database()
    db_manager.migrate_existing_data()


if __name__ == '__main__':
    # Тестирование создания БД
    init_db()
