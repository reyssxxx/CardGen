"""
Репозиторий для работы с пользователями
"""
import sqlite3
from typing import Optional, Tuple
from database.db_manager import DatabaseManager


class UserRepository:
    def __init__(self, db_path='./data/database.db'):
        self.db_manager = DatabaseManager(db_path)

    def get_user(self, user_id: int) -> Optional[Tuple[str, bool]]:
        """
        Получить пользователя по Telegram ID
        Возвращает: (ФИ, isTeacher) или None
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'SELECT ФИ, isTeacher FROM Users WHERE ID=?',
                (user_id,)
            )
            result = cursor.fetchone()

            if result:
                return (result['ФИ'], bool(result['isTeacher']))
            return None

        finally:
            conn.close()

    def get_user_by_name(self, name: str) -> Optional[dict]:
        """
        Получить пользователя по ФИО
        Возвращает: {'ID': int, 'ФИ': str, 'isTeacher': bool, 'role': str} или None
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'SELECT ID, ФИ, isTeacher FROM Users WHERE ФИ=?',
                (name,)
            )
            result = cursor.fetchone()

            if result:
                is_teacher = bool(result['isTeacher'])
                return {
                    'ID': result['ID'],
                    'ФИ': result['ФИ'],
                    'isTeacher': is_teacher,
                    'role': 'teacher' if is_teacher else 'student'
                }
            return None

        finally:
            conn.close()

    def register_user(self, name: str, user_id: int, is_teacher: bool) -> bool:
        """
        Зарегистрировать нового пользователя
        Возвращает: True если успешно, False если пользователь уже существует
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'INSERT INTO Users (ФИ, ID, isTeacher) VALUES (?, ?, ?)',
                (name, user_id, is_teacher)
            )
            conn.commit()
            return True

        except sqlite3.IntegrityError:
            # Пользователь уже существует
            return False
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def check_name_exists(self, name: str) -> bool:
        """
        Проверить существование пользователя по ФИО
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'SELECT 1 FROM Users WHERE ФИ=? LIMIT 1',
                (name,)
            )
            return cursor.fetchone() is not None

        finally:
            conn.close()

    def get_all_students(self) -> list:
        """
        Получить всех учеников
        Возвращает: список (user_id, name)
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'SELECT ID, ФИ FROM Users WHERE isTeacher=0 ORDER BY ФИ'
            )
            return [(row['ID'], row['ФИ']) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_all_teachers(self) -> list:
        """
        Получить всех учителей
        Возвращает: список (user_id, name)
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                'SELECT ID, ФИ FROM Users WHERE isTeacher=1 ORDER BY ФИ'
            )
            return [(row['ID'], row['ФИ']) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_students_by_class(self, class_name: str) -> list:
        """
        Получить учеников определенного класса
        Примечание: класс не хранится в Users, нужно смотреть students.json
        Эта функция для будущего расширения
        """
        # TODO: Реализовать после добавления класса в таблицу Users
        pass
