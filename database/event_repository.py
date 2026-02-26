"""
Репозиторий для работы с мероприятиями и регистрациями.
"""
import json
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

    def create_event(self, title: str, date: str, time_slots: list,
                     created_by: int, class_limit: Optional[int] = None,
                     description: Optional[str] = None) -> int:
        """Создать мероприятие. Возвращает id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Events (title, description, date, time_slots, class_limit, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (title, description, date, json.dumps(time_slots, ensure_ascii=False),
                  class_limit, created_by))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_active_events(self) -> list:
        """Получить все активные мероприятия."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM Events WHERE is_active = 1 ORDER BY date ASC
            ''')
            rows = cursor.fetchall()
            return [self._parse_event(row) for row in rows]
        finally:
            conn.close()

    def get_all_events(self) -> list:
        """Получить все мероприятия (для админа)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM Events ORDER BY is_active DESC, date DESC
            ''')
            rows = cursor.fetchall()
            return [self._parse_event(row) for row in rows]
        finally:
            conn.close()

    def get_event(self, event_id: int) -> Optional[dict]:
        """Получить мероприятие по id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Events WHERE id = ?', (event_id,))
            row = cursor.fetchone()
            return self._parse_event(row) if row else None
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

    def _parse_event(self, row) -> dict:
        d = dict(row)
        d['time_slots'] = json.loads(d['time_slots'])
        return d

    # ── Регистрации ───────────────────────────────────────────────────────────

    def register(self, event_id: int, user_id: int, time_slot: str,
                 student_name: str, class_name: str) -> bool:
        """
        Зарегистрировать ученика на слот.
        Возвращает True при успехе, False если уже зарегистрирован.
        """
        conn = self._conn()
        try:
            conn.execute('''
                INSERT INTO EventRegistrations (event_id, user_id, time_slot, student_name, class)
                VALUES (?, ?, ?, ?, ?)
            ''', (event_id, user_id, time_slot, student_name, class_name))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def unregister(self, event_id: int, user_id: int, time_slot: str):
        """Отменить запись ученика на слот."""
        conn = self._conn()
        try:
            conn.execute('''
                DELETE FROM EventRegistrations
                WHERE event_id = ? AND user_id = ? AND time_slot = ?
            ''', (event_id, user_id, time_slot))
            conn.commit()
        finally:
            conn.close()

    def get_user_registrations(self, event_id: int, user_id: int) -> list[str]:
        """Получить список слотов, на которые записан пользователь."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT time_slot FROM EventRegistrations
                WHERE event_id = ? AND user_id = ?
            ''', (event_id, user_id))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_class_slot_count(self, event_id: int, time_slot: str, class_name: str) -> int:
        """Количество зарегистрированных от данного класса на слот."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM EventRegistrations
                WHERE event_id = ? AND time_slot = ? AND class = ?
            ''', (event_id, time_slot, class_name))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def is_slot_available(self, event_id: int, time_slot: str,
                          class_name: str, class_limit: Optional[int]) -> bool:
        """Проверить, есть ли свободные места от класса на слот."""
        if class_limit is None:
            return True
        count = self.get_class_slot_count(event_id, time_slot, class_name)
        return count < class_limit

    def get_registrations_by_event(self, event_id: int) -> dict:
        """
        Получить все регистрации для мероприятия.
        Возвращает: {time_slot: [{student_name, class}, ...]}
        """
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT time_slot, student_name, class
                FROM EventRegistrations
                WHERE event_id = ?
                ORDER BY time_slot, class, student_name
            ''', (event_id,))
            result = {}
            for row in cursor.fetchall():
                slot = row[0]
                if slot not in result:
                    result[slot] = []
                result[slot].append({'student_name': row[1], 'class': row[2]})
            return result
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
