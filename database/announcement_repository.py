"""
Репозиторий для объявлений.
"""
import sqlite3
from typing import Optional


class AnnouncementRepository:
    def __init__(self, db_path='./data/database.db'):
        self.db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, text: str, created_by: int, target: str = 'all',
               photo_file_id: Optional[str] = None) -> int:
        """Создать объявление. Возвращает id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Announcements (text, target, created_by, photo_file_id)
                VALUES (?, ?, ?, ?)
            ''', (text, target, created_by, photo_file_id))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_by_teacher(self, user_id: int, limit: int = 10) -> list:
        """Получить объявления конкретного учителя (по created_by)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.*, u.ФИ as author_name
                FROM Announcements a
                LEFT JOIN Users u ON a.created_by = u.ID
                WHERE a.created_by = ?
                ORDER BY a.created_at DESC LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_recent(self, limit: int = 10, target: Optional[str] = None) -> list:
        """
        Получить последние объявления с информацией об авторе.
        target: None — все, '11Т' — для класса (включает общие).
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            if target is None:
                cursor.execute('''
                    SELECT a.*, u.ФИ as author_name, u.isTeacher as author_is_teacher
                    FROM Announcements a
                    LEFT JOIN Users u ON a.created_by = u.ID
                    ORDER BY a.created_at DESC LIMIT ?
                ''', (limit,))
            else:
                cursor.execute('''
                    SELECT a.*, u.ФИ as author_name, u.isTeacher as author_is_teacher
                    FROM Announcements a
                    LEFT JOIN Users u ON a.created_by = u.ID
                    WHERE a.target = 'all' OR a.target = ?
                    ORDER BY a.created_at DESC LIMIT ?
                ''', (target, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
