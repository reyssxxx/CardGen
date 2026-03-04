"""
Репозиторий для тикетов (обращений учеников к администрации).
"""
import sqlite3
from typing import Optional


class TicketRepository:
    def __init__(self, db_path='./data/database.db'):
        self.db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, student_user_id: int, student_name: str,
               student_class: str, title: str) -> int:
        """Создать тикет. Возвращает id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO Tickets (student_user_id, student_name, student_class, title)
                VALUES (?, ?, ?, ?)
            ''', (student_user_id, student_name, student_class, title))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def add_message(self, ticket_id: int, sender_type: str,
                    sender_name: str, text: str) -> int:
        """Добавить сообщение в тикет. Возвращает id сообщения."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO TicketMessages (ticket_id, sender_type, sender_name, text)
                VALUES (?, ?, ?, ?)
            ''', (ticket_id, sender_type, sender_name, text))
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_messages(self, ticket_id: int) -> list:
        """Получить все сообщения тикета в хронологическом порядке."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM TicketMessages
                WHERE ticket_id = ?
                ORDER BY created_at ASC
            ''', (ticket_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_ticket(self, ticket_id: int) -> Optional[dict]:
        """Получить тикет по id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM Tickets WHERE id = ?', (ticket_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_by_student(self, student_user_id: int) -> list:
        """Получить все тикеты студента (сначала открытые, потом закрытые)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM Tickets
                WHERE student_user_id = ?
                ORDER BY
                    CASE WHEN status = 'open' THEN 0 ELSE 1 END,
                    created_at DESC
            ''', (student_user_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_open(self) -> list:
        """Получить все открытые тикеты, отсортированные по последнему сообщению."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*,
                    (SELECT text FROM TicketMessages
                     WHERE ticket_id = t.id ORDER BY created_at DESC LIMIT 1) as last_msg,
                    (SELECT created_at FROM TicketMessages
                     WHERE ticket_id = t.id ORDER BY created_at DESC LIMIT 1) as last_msg_at
                FROM Tickets t
                WHERE t.status = 'open'
                ORDER BY last_msg_at DESC NULLS LAST, t.created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all_closed(self) -> list:
        """Получить все закрытые тикеты."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM Tickets
                WHERE status = 'closed'
                ORDER BY closed_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def close(self, ticket_id: int):
        """Закрыть тикет."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE Tickets
                SET status = 'closed', closed_at = datetime('now', 'localtime')
                WHERE id = ?
            ''', (ticket_id,))
            conn.commit()
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """Статистика тикетов."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END) as open,
                    SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed
                FROM Tickets
            ''')
            row = cursor.fetchone()
            return dict(row) if row else {'total': 0, 'open': 0, 'closed': 0}
        finally:
            conn.close()
