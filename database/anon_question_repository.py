"""
Репозиторий для вопросов учеников.
"""
import sqlite3
from typing import Optional


class AnonQuestionRepository:
    def __init__(self, db_path='./data/database.db'):
        self.db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create(self, text: str, asker_user_id: int = None,
               photo_file_id: str = None) -> int:
        """Сохранить вопрос. Возвращает id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO AnonQuestions (text, asker_user_id, photo_file_id) VALUES (?, ?, ?)',
                (text, asker_user_id, photo_file_id),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()

    def get_unanswered(self) -> list:
        """Получить все неотвеченные вопросы."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM AnonQuestions
                WHERE answered = 0
                ORDER BY created_at ASC
            ''')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_all(self) -> list:
        """Получить все вопросы с информацией об авторе (неотвеченные первыми)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT q.*, u.ФИ as author_name, u.class as author_class
                FROM AnonQuestions q
                LEFT JOIN Users u ON q.asker_user_id = u.ID
                ORDER BY q.answered ASC, q.created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_by_id(self, question_id: int) -> Optional[dict]:
        """Получить вопрос по id с информацией об авторе."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT q.*, u.ФИ as author_name, u.class as author_class
                FROM AnonQuestions q
                LEFT JOIN Users u ON q.asker_user_id = u.ID
                WHERE q.id = ?
            ''', (question_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_by_user(self, user_id: int) -> list:
        """Получить все вопросы конкретного ученика."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM AnonQuestions
                WHERE asker_user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def answer(self, question_id: int, answer_text: str,
               answer_photo_file_id: str = None):
        """Отметить вопрос как отвеченный и сохранить ответ."""
        conn = self._conn()
        try:
            conn.execute('''
                UPDATE AnonQuestions
                SET answered = 1, answer = ?, answer_photo_file_id = ?
                WHERE id = ?
            ''', (answer_text, answer_photo_file_id, question_id))
            conn.commit()
        finally:
            conn.close()

    def delete(self, question_id: int):
        """Удалить вопрос."""
        conn = self._conn()
        try:
            conn.execute('DELETE FROM AnonQuestions WHERE id = ?', (question_id,))
            conn.commit()
        finally:
            conn.close()
