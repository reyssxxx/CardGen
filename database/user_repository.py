"""
Репозиторий для работы с пользователями.
"""
import os
import sqlite3
from typing import Optional
from database.db_manager import DatabaseManager
from dotenv import load_dotenv

_ADMIN_IDS_CACHE: set | None = None


def _get_admin_ids() -> set:
    global _ADMIN_IDS_CACHE
    if _ADMIN_IDS_CACHE is None:
        load_dotenv(override=True)
        _ADMIN_IDS_CACHE = {int(x) for x in os.getenv("ADMIN_ID", "").split(",") if x.strip()}
    return _ADMIN_IDS_CACHE


class UserRepository:
    def __init__(self, db_path='./data/database.db'):
        self.db_manager = DatabaseManager(db_path)

    def _conn(self):
        return self.db_manager.get_connection()

    def get_user(self, user_id: int) -> Optional[dict]:
        """
        Получить пользователя по Telegram ID.
        isAdmin определяется по .env ADMIN_ID (не из БД) — источник истины.
        Возвращает: {'ФИ': str, 'class': str, 'isAdmin': bool, 'isTeacher': bool} или None.
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT ФИ, class, isAdmin, isTeacher FROM Users WHERE ID = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'ФИ': row['ФИ'],
                    'class': row['class'],
                    'isAdmin': user_id in _get_admin_ids(),
                    'isTeacher': bool(row['isTeacher']),
                }
            return None
        finally:
            conn.close()

    def register_student(self, name: str, user_id: int, class_name: str) -> bool:
        """
        Зарегистрировать ученика.
        Возвращает False если имя уже занято другим пользователем.
        """
        conn = self._conn()
        try:
            # Проверить, не занято ли ФИО
            cursor = conn.cursor()
            cursor.execute('SELECT ID FROM Users WHERE ФИ = ?', (name,))
            existing = cursor.fetchone()
            if existing and existing['ID'] != user_id:
                return False

            cursor.execute('''
                INSERT OR REPLACE INTO Users (ID, ФИ, class, isAdmin)
                VALUES (?, ?, ?, 0)
            ''', (user_id, name, class_name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def register_admin(self, name: str, user_id: int) -> bool:
        """Зарегистрировать/обновить администратора."""
        conn = self._conn()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO Users (ID, ФИ, class, isAdmin, isTeacher)
                VALUES (?, ?, '', 1, 0)
            ''', (user_id, name))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def register_teacher(self, name: str, user_id: int) -> bool:
        """Зарегистрировать/обновить учителя."""
        conn = self._conn()
        try:
            conn.execute('''
                INSERT OR REPLACE INTO Users (ID, ФИ, class, isAdmin, isTeacher)
                VALUES (?, ?, '', 0, 1)
            ''', (user_id, name))
            conn.commit()
            return True
        except Exception:
            return False
        finally:
            conn.close()

    def is_teacher(self, user_id: int) -> bool:
        """Проверить, является ли пользователь учителем."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT isTeacher FROM Users WHERE ID = ?', (user_id,))
            row = cursor.fetchone()
            return bool(row['isTeacher']) if row else False
        finally:
            conn.close()

    def get_all_teachers(self) -> list:
        """Получить всех учителей — список (user_id, name)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT ID, ФИ FROM Users WHERE isTeacher = 1')
            return [(row['ID'], row['ФИ']) for row in cursor.fetchall()]
        finally:
            conn.close()

    def is_admin(self, user_id: int) -> bool:
        """Проверить, является ли пользователь администратором (по .env)."""
        return user_id in _get_admin_ids()

    def _is_admin_legacy(self, user_id: int) -> bool:
        """Проверка по БД — только для внутреннего использования."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT isAdmin FROM Users WHERE ID = ?', (user_id,))
            row = cursor.fetchone()
            return bool(row['isAdmin']) if row else False
        finally:
            conn.close()

    def is_name_taken(self, name: str) -> bool:
        """Проверить, зарегистрировано ли ФИО."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM Users WHERE ФИ = ?', (name,))
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_all_students(self) -> list:
        """Получить всех учеников — список (user_id, name, class)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT ID, ФИ, class FROM Users WHERE isAdmin = 0 AND isTeacher = 0 ORDER BY class, ФИ'
            )
            return [(row['ID'], row['ФИ'], row['class']) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_students_by_class(self, class_name: str) -> list:
        """Получить учеников класса — список (user_id, name)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT ID, ФИ FROM Users WHERE isAdmin = 0 AND isTeacher = 0 AND class = ? ORDER BY ФИ',
                (class_name,)
            )
            return [(row['ID'], row['ФИ']) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_admins(self) -> list:
        """Получить всех администраторов из .env — список (user_id, name)."""
        admin_ids = _get_admin_ids()
        conn = self._conn()
        try:
            cursor = conn.cursor()
            result = []
            for uid in admin_ids:
                cursor.execute('SELECT ФИ FROM Users WHERE ID = ?', (uid,))
                row = cursor.fetchone()
                name = row['ФИ'] if row else "Администратор"
                result.append((uid, name))
            return result
        finally:
            conn.close()
