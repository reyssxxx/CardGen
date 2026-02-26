"""
Репозиторий для анонимных вопросов.
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

    def create(self, text: str) -> int:
        """Сохранить вопрос. Возвращает id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO AnonQuestions (text) VALUES (?)', (text,))
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
        """Получить все вопросы (неотвеченные первыми)."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM AnonQuestions
                ORDER BY answered ASC, created_at ASC
            ''')
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_by_id(self, question_id: int) -> Optional[dict]:
        """Получить вопрос по id."""
        conn = self._conn()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM AnonQuestions WHERE id = ?', (question_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def answer(self, question_id: int, answer_text: str):
        """Отметить вопрос как отвеченный и сохранить ответ."""
        conn = self._conn()
        try:
            conn.execute('''
                UPDATE AnonQuestions
                SET answered = 1, answer = ?
                WHERE id = ?
            ''', (answer_text, question_id))
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
