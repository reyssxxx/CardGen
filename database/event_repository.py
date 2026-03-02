"""
Репозиторий для работы с мероприятиями и регистрациями.
"""
import sqlite3
from typing import Optional


class EventRepository:
    def __init__(self, db_path='./data/database.db'):
        self.db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Мероприятия ──────────────────────────────────────────────────────────

    def create_event(self, title: str, date: str, created_by: int,
                     class_limit: Optional[int] = None,
                     description: Optional[str] = None) -> int:
        """Создать мероприятие. Возвращает id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Events (title, description, date, time_slots, class_limit, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, description, date, '[]', class_limit, created_by))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_active_events(self) -> list:
        """Получить все активные мероприятия."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Events WHERE is_active = 1 ORDER BY date ASC')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_events(self) -> list:
        """Получить все мероприятия (для админа)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Events ORDER BY is_active DESC, date DESC')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_event(self, event_id: int) -> Optional[dict]:
        """Получить мероприятие по id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Events WHERE id = ?', (event_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def deactivate_event(self, event_id: int):
        """Деактивировать (архивировать) мероприятие."""
        conn = self._conn()
        try:
            conn.execute('UPDATE Events SET is_active = 0 WHERE id = ?', (event_id,))
            conn.commit()
        finally:
            conn.close()

    # ── Регистрации ───────────────────────────────────────────────────────────

    def register(self, event_id: int, user_id: int,
                 student_name: str, class_name: str) -> bool:
        """
        Зарегистрировать ученика на мероприятие.
        Возвращает True при успехе, False если уже зарегистрирован.
        """
        conn = self._conn()
        try:
            conn.execute('''
                INSERT INTO EventRegistrations (event_id, user_id, time_slot, student_name, class)
                VALUES (?, ?, ?, ?, ?)
            ''', (event_id, user_id, '', student_name, class_name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def unregister_from_event(self, event_id: int, user_id: int):
        """Отменить запись ученика на мероприятие."""
        conn = self._conn()
        try:
            conn.execute(
                'DELETE FROM EventRegistrations WHERE event_id = ? AND user_id = ?',
                (event_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()

    def is_registered(self, event_id: int, user_id: int) -> bool:
        """Проверить, записан ли пользователь на мероприятие."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM EventRegistrations WHERE event_id = ? AND user_id = ?',
                (event_id, user_id),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def is_event_available(self, event_id: int, class_name: str, class_limit) -> bool:
        """Есть ли свободные места от класса."""
        if not class_limit:
            return True
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM EventRegistrations WHERE event_id = ? AND class = ?',
                (event_id, class_name),
            )
            return cursor.fetchone()[0] < class_limit
        finally:
            conn.close()

    def get_all_registrations(self, event_id: int) -> list:
        """Получить плоский список всех записавшихся на мероприятие."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT student_name, class
                FROM EventRegistrations
                WHERE event_id = ?
                ORDER BY class, student_name
            ''', (event_id,))
            return [{'student_name': row[0], 'class': row[1]} for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_total_registrations(self, event_id: int) -> int:
        """Общее число регистраций на мероприятие."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM EventRegistrations WHERE event_id = ?', (event_id,))
            return cursor.fetchone()[0]
        finally:
            conn.close()
