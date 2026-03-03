"""
Репозиторий для работы с мероприятиями, секциями и регистрациями.
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

    # ── Мероприятия (дни) ────────────────────────────────────────────────────

    def create_event(self, title: str, date: str, created_by: int,
                     description: Optional[str] = None,
                     class_limit: Optional[int] = None) -> int:
        """Создать день мероприятий (черновик). Возвращает id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Events (title, description, date, time_slots, class_limit, created_by, published)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            ''', (title, description, date, '[]', class_limit, created_by))
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
        """Получить все активные опубликованные мероприятия (для учеников)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM Events WHERE is_active = 1 AND published = 1 ORDER BY date ASC'
            )
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

    def delete_event(self, event_id: int):
        """Полностью удалить мероприятие, все секции и регистрации."""
        conn = self._conn()
        try:
            conn.execute('DELETE FROM EventRegistrations WHERE event_id = ?', (event_id,))
            conn.execute('DELETE FROM EventSections WHERE event_id = ?', (event_id,))
            conn.execute('DELETE FROM Events WHERE id = ?', (event_id,))
            conn.commit()
        finally:
            conn.close()

    # ── Секции ───────────────────────────────────────────────────────────────

    def add_section(self, event_id: int, title: str, host: str = None,
                    time: str = None, description: str = None,
                    capacity: int = None) -> int:
        """Добавить секцию к мероприятию. Возвращает id секции."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO EventSections (event_id, title, host, time, description, capacity, sort_order)
                VALUES (?, ?, ?, ?, ?, ?, (SELECT COALESCE(MAX(sort_order)+1, 0) FROM EventSections WHERE event_id = ?))
            ''', (event_id, title, host, time, description, capacity, event_id))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_sections(self, event_id: int) -> list:
        """Получить все секции мероприятия."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM EventSections WHERE event_id = ? ORDER BY sort_order, time',
                (event_id,)
            )
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
        """Удалить секцию (и связанные регистрации)."""
        conn = self._conn()
        try:
            conn.execute('DELETE FROM EventRegistrations WHERE section_id = ?', (section_id,))
            conn.execute('DELETE FROM EventSections WHERE id = ?', (section_id,))
            conn.commit()
        finally:
            conn.close()

    def get_section_registrations(self, section_id: int) -> list:
        """Все зарегистрированные на секцию."""
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

    def get_section_count(self, section_id: int) -> int:
        """Число записавшихся на секцию."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COUNT(*) FROM EventRegistrations WHERE section_id = ?', (section_id,))
            return cursor.fetchone()[0]
        finally:
            conn.close()

    # ── Регистрации ──────────────────────────────────────────────────────────

    def register_to_section(self, event_id: int, section_id: int,
                             user_id: int, student_name: str, class_name: str) -> bool:
        """
        Записать ученика на конкретную секцию.
        Ученик может быть записан на несколько секций одного мероприятия.
        Если уже записан на эту секцию — ничего не делает, возвращает False.
        """
        conn = self._conn()
        try:
            # Проверяем, не записан ли уже на эту конкретную секцию
            cursor = conn.cursor()
            cursor.execute(
                'SELECT 1 FROM EventRegistrations WHERE event_id = ? AND user_id = ? AND section_id = ?',
                (event_id, user_id, section_id),
            )
            if cursor.fetchone():
                return False
            conn.execute('''
                INSERT INTO EventRegistrations (event_id, user_id, time_slot, student_name, class, section_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (event_id, user_id, '', student_name, class_name, section_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def register(self, event_id: int, user_id: int,
                 student_name: str, class_name: str) -> bool:
        """Записать ученика на мероприятие без секции (старый формат)."""
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

    def get_user_section(self, event_id: int, user_id: int) -> Optional[int]:
        """Вернуть section_id первой записи пользователя (обратная совместимость)."""
        sections = self.get_user_sections(event_id, user_id)
        return sections[0] if sections else None

    def get_user_sections(self, event_id: int, user_id: int) -> list:
        """Вернуть список section_id, на которые записан пользователь."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT section_id FROM EventRegistrations WHERE event_id = ? AND user_id = ? AND section_id IS NOT NULL',
                (event_id, user_id),
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def unregister_from_section(self, event_id: int, section_id: int, user_id: int):
        """Отменить запись ученика на конкретную секцию."""
        conn = self._conn()
        try:
            conn.execute(
                'DELETE FROM EventRegistrations WHERE event_id = ? AND section_id = ? AND user_id = ?',
                (event_id, section_id, user_id),
            )
            conn.commit()
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
                SELECT student_name, class FROM EventRegistrations
                WHERE event_id = ? ORDER BY class, student_name
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

    def get_user_events(self, user_id: int) -> list:
        """Активные мероприятия, на которые записан пользователь."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT Events.*
                FROM Events
                JOIN EventRegistrations ON Events.id = EventRegistrations.event_id
                WHERE EventRegistrations.user_id = ? AND Events.is_active = 1
                ORDER BY Events.date ASC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_registered_user_ids(self, event_id: int) -> list:
        """Список user_id всех записавшихся на мероприятие."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT user_id FROM EventRegistrations WHERE event_id = ?', (event_id,))
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_events_for_date(self, date_str: str) -> list:
        """Активные мероприятия на указанную дату."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM Events WHERE date = ? AND is_active = 1', (date_str,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_expired_active_events(self) -> list:
        """Активные мероприятия с уже прошедшей датой."""
        from datetime import date as date_cls, datetime
        today = date_cls.today()
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Events WHERE is_active = 1')
            expired = []
            for row in cursor.fetchall():
                event = dict(row)
                try:
                    event_date = datetime.strptime(event['date'], '%d.%m.%Y').date()
                    if event_date < today:
                        expired.append(event)
                except ValueError:
                    pass
            return expired
        finally:
            conn.close()
