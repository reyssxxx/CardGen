"""
Менеджер базы данных - создание таблиц и миграции
"""
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path='./data/database.db'):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self):
        """Получить подключение к БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """Инициализация всех таблиц БД"""
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # Ученики, учителя и администраторы
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Users (
                    ID INTEGER PRIMARY KEY,
                    ФИ TEXT NOT NULL,
                    class TEXT NOT NULL DEFAULT '',
                    isAdmin BOOLEAN NOT NULL DEFAULT 0,
                    isTeacher BOOLEAN NOT NULL DEFAULT 0
                )
            ''')

            # Миграции для существующих БД
            for migration in [
                'ALTER TABLE Users ADD COLUMN class TEXT NOT NULL DEFAULT ""',
                'ALTER TABLE Users ADD COLUMN isAdmin BOOLEAN NOT NULL DEFAULT 0',
                'ALTER TABLE Users ADD COLUMN isTeacher BOOLEAN NOT NULL DEFAULT 0',
            ]:
                try:
                    cursor.execute(migration)
                except sqlite3.OperationalError:
                    pass

            # Оценки
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Grades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_name TEXT NOT NULL,
                    class TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    date DATE NOT NULL,
                    uploaded_by INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (student_name) REFERENCES Users(ФИ)
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_grades_student
                ON Grades(student_name, date)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_grades_subject_class
                ON Grades(class, subject, date)
            ''')

            # Уникальный индекс: защита от дублей при повторной загрузке Excel
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_grades_unique
                ON Grades(student_name, subject, date, grade)
            ''')

            # Мероприятия
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    date TEXT NOT NULL,
                    time_slots TEXT NOT NULL,
                    class_limit INTEGER,
                    created_by INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Секции мероприятий
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS EventSections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL REFERENCES Events(id),
                    title TEXT NOT NULL,
                    host TEXT,
                    time TEXT,
                    description TEXT,
                    capacity INTEGER,
                    sort_order INTEGER DEFAULT 0
                )
            ''')

            # Регистрации на мероприятия
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS EventRegistrations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL REFERENCES Events(id),
                    user_id INTEGER NOT NULL,
                    time_slot TEXT NOT NULL,
                    student_name TEXT NOT NULL,
                    class TEXT NOT NULL,
                    section_id INTEGER REFERENCES EventSections(id),
                    registered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(event_id, user_id, time_slot)
                )
            ''')

            # Объявления
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS Announcements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    target TEXT DEFAULT 'all',
                    created_by INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Вопросы учеников
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS AnonQuestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    text TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    answered BOOLEAN DEFAULT 0,
                    answer TEXT,
                    asker_user_id INTEGER
                )
            ''')

            # Миграции для существующих БД
            for migration in [
                'ALTER TABLE AnonQuestions ADD COLUMN asker_user_id INTEGER',
                'ALTER TABLE AnonQuestions ADD COLUMN photo_file_id TEXT',
                'ALTER TABLE AnonQuestions ADD COLUMN answer_photo_file_id TEXT',
                'ALTER TABLE Announcements ADD COLUMN photo_file_id TEXT',
                'ALTER TABLE Events ADD COLUMN published BOOLEAN DEFAULT 1',
                'ALTER TABLE EventRegistrations ADD COLUMN section_id INTEGER REFERENCES EventSections(id)',
            ]:
                try:
                    cursor.execute(migration)
                except sqlite3.OperationalError:
                    pass

            # Анонимные чаты психологической поддержки
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS SupportChats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_user_id INTEGER NOT NULL,
                    is_anonymous INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now', 'localtime')),
                    closed_at TEXT
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_support_chats_student
                ON SupportChats(student_user_id, status)
            ''')

            # Сообщения в чатах поддержки
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS SupportMessages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL REFERENCES SupportChats(id),
                    sender_type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now', 'localtime'))
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_support_messages_chat
                ON SupportMessages(chat_id, created_at)
            ''')

            conn.commit()
            logger.info("Database initialized successfully")

        except Exception as e:
            conn.rollback()
            logger.exception("Database initialization failed: %s", e)
            raise
        finally:
            conn.close()


def init_db():
    """Инициализировать БД — вызывается при запуске бота"""
    db_manager = DatabaseManager()
    db_manager.init_database()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    init_db()
