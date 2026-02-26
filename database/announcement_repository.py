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

    def create(self, text: str, created_by: int, target: str = 'all') -> int:
        """Создать объявление. Возвращает id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Announcements (text, target, created_by)
                VALUES (?, ?, ?)
            ''', (text, target, created_by))
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
                SELECT * FROM Announcements
                WHERE created_by = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_recent(self, limit: int = 5, target: Optional[str] = None) -> list:
        """
        Получить последние объявления.
        target: None — все, 'all' — общие, '11Т' — для класса.
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            if target is None:
                cursor.execute('''
                    SELECT * FROM Announcements
                    ORDER BY created_at DESC LIMIT ?
                ''', (limit,))
            else:
                cursor.execute('''
                    SELECT * FROM Announcements
                    WHERE target = 'all' OR target = ?
                    ORDER BY created_at DESC LIMIT ?
                ''', (target, limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
