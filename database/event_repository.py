"""
Репозиторий для работы с мероприятиями, секциями и регистрациями.
"""
import json
import sqlite3
from datetime import datetime
from typing import Optional


class EventRepository:
    def __init__(self, db_path='./data/database.db'):
        self.db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Мероприятия (дни) ────────────────────────────────────────────────────

    def create_event(self, title: str, date: str, created_by: int,
                     description: Optional[str] = None,
                     time_slots: Optional[list] = None,
                     class_limit: Optional[int] = None) -> int:
        """Создать мероприятие (день). Возвращает id. published=0 по умолчанию."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            slots = json.dumps(time_slots or [""], ensure_ascii=False)
            cursor.execute('''
                INSERT INTO Events (title, description, date, time_slots, class_limit, created_by, published)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', (title, description, date, slots, class_limit, created_by))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def publish_event(self, event_id: int):
        """Опубликовать мероприятие (сделать видимым для учеников)."""
        conn = self._conn()
        try:
            conn.execute('UPDATE Events SET published = 1 WHERE id = ?', (event_id,))
            conn.commit()
        finally:
            conn.close()

    def get_active_events(self) -> list:
        """Получить все активные опубликованные мероприятия (сегодня и позже)."""
        conn = self._conn()
        try:
            today = datetime.now().date()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Events WHERE is_active = 1 AND published = 1 ORDER BY date ASC')
            rows = cursor.fetchall()
            events = []
            for row in rows:
                event = self._parse_event(row)
                try:
                    event_date = datetime.strptime(event["date"], "%d.%m.%Y").date()
                except ValueError:
                    events.append(event)
                    continue
                if event_date >= today:
                    events.append(event)
            return events
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

    def delete_event(self, event_id: int):
        """Полностью удалить мероприятие, все его секции и регистрации."""
        conn = self._conn()
        try:
            conn.execute('DELETE FROM EventRegistrations WHERE event_id = ?', (event_id,))
            conn.execute('DELETE FROM EventSections WHERE event_id = ?', (event_id,))
            conn.execute('DELETE FROM Events WHERE id = ?', (event_id,))
            conn.commit()
        finally:
            conn.close()

    def _parse_event(self, row) -> dict:
        d = dict(row)
        d['time_slots'] = json.loads(d['time_slots'])
        return d

    # ── Секции ───────────────────────────────────────────────────────────────

    def add_section(self, event_id: int, title: str, host: Optional[str] = None,
                    time: Optional[str] = None, description: Optional[str] = None,
                    capacity: Optional[int] = None) -> int:
        """Добавить секцию к мероприятию. Возвращает id секции."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            # sort_order = текущее кол-во секций
            cursor.execute('SELECT COUNT(*) FROM EventSections WHERE event_id = ?', (event_id,))
            sort_order = cursor.fetchone()[0]
            cursor.execute('''
                INSERT INTO EventSections (event_id, title, host, time, description, capacity, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (event_id, title, host, time, description, capacity, sort_order))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_sections(self, event_id: int) -> list:
        """Получить все секции мероприятия."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM EventSections WHERE event_id = ? ORDER BY sort_order ASC
            ''', (event_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_section(self, section_id: int) -> Optional[dict]:
        """Получить секцию по id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM EventSections WHERE id = ?', (section_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_section(self, section_id: int):
        """Удалить секцию и все регистрации на неё."""
        conn = self._conn()
        try:
            conn.execute('DELETE FROM EventRegistrations WHERE section_id = ?', (section_id,))
            conn.execute('DELETE FROM EventSections WHERE id = ?', (section_id,))
            conn.commit()
        finally:
            conn.close()

    # ── Регистрации ──────────────────────────────────────────────────────────

    def register_section(self, event_id: int, section_id: int, user_id: int,
                         student_name: str, class_name: str) -> bool:
        """Записать ученика на секцию. Возвращает True при успехе."""
        conn = self._conn()
        try:
            conn.execute('''
                INSERT INTO EventRegistrations (event_id, user_id, time_slot, student_name, class, section_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (event_id, user_id, str(section_id), student_name, class_name, section_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def unregister_section(self, section_id: int, user_id: int):
        """Отменить запись ученика с секции."""
        conn = self._conn()
        try:
            conn.execute('''
                DELETE FROM EventRegistrations WHERE section_id = ? AND user_id = ?
            ''', (section_id, user_id))
            conn.commit()
        finally:
            conn.close()

    def is_registered_section(self, section_id: int, user_id: int) -> bool:
        """Проверить, записан ли ученик на секцию."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM EventRegistrations WHERE section_id = ? AND user_id = ?',
                (section_id, user_id),
            )
            return cursor.fetchone() is not None
        finally:
            conn.close()

    def get_section_registration_count(self, section_id: int) -> int:
        """Общее число записавшихся на секцию."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM EventRegistrations WHERE section_id = ?', (section_id,))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def is_section_available(self, section_id: int) -> bool:
        """Есть ли свободные места на секции (по capacity)."""
        section = self.get_section(section_id)
        if not section or section["capacity"] is None:
            return True
        count = self.get_section_registration_count(section_id)
        return count < section["capacity"]

    def get_user_sections(self, event_id: int, user_id: int) -> list:
        """Получить список section_id, на которые записан ученик в рамках мероприятия."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT section_id FROM EventRegistrations
                WHERE event_id = ? AND user_id = ? AND section_id IS NOT NULL
            ''', (event_id, user_id))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_section_registrations(self, section_id: int) -> list:
        """Получить список записавшихся на секцию."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT student_name, class FROM EventRegistrations
                WHERE section_id = ? ORDER BY class, student_name
            ''', (section_id,))
            return [{'student_name': row[0], 'class': row[1]} for row in cursor.fetchall()]
        finally:
            conn.close()

    # ── Обратная совместимость (старые мероприятия без секций) ────────────────

    def register(self, event_id: int, user_id: int, time_slot: str,
                 student_name: str, class_name: str) -> bool:
        """Старый метод регистрации (без секций)."""
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

    def is_registered(self, event_id: int, user_id: int) -> bool:
        """Проверить, записан ли пользователь на мероприятие (любая секция)."""
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
        """Есть ли свободные места от класса (старые мероприятия без секций)."""
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

    def unregister_from_event(self, event_id: int, user_id: int):
        """Отменить все записи ученика на мероприятие."""
        conn = self._conn()
        try:
            conn.execute(
                'DELETE FROM EventRegistrations WHERE event_id = ? AND user_id = ?',
                (event_id, user_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_registrations_by_event(self, event_id: int) -> dict:
        """Получить все регистрации: {slot: [{student_name, class}]}."""
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
