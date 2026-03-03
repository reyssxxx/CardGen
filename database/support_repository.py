"""
Репозиторий для анонимных чатов психологической поддержки.
"""
import logging
from typing import List, Dict, Optional

from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class SupportRepository:
    def __init__(self, db_path: str = './data/database.db'):
        self.db = DatabaseManager(db_path)

    # ── Чаты ──────────────────────────────────────────────────────────────────

    def create_chat(self, student_user_id: int) -> int:
        """Создать новый активный анонимный чат. Возвращает ID чата."""
        conn = self.db.get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO SupportChats (student_user_id) VALUES (?)",
                (student_user_id,),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_active_chat(self, student_user_id: int) -> Optional[Dict]:
        """Получить активный чат студента или None."""
        conn = self.db.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM SupportChats WHERE student_user_id=? AND status='active'",
                (student_user_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_chat(self, chat_id: int) -> Optional[Dict]:
        """Получить чат по ID."""
        conn = self.db.get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM SupportChats WHERE id=?", (chat_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def close_chat(self, chat_id: int) -> None:
        """Закрыть чат."""
        conn = self.db.get_connection()
        try:
            conn.execute(
                "UPDATE SupportChats SET status='closed', closed_at=datetime('now','localtime') WHERE id=?",
                (chat_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def reveal_identity(self, chat_id: int) -> None:
        """Снять анонимность с чата."""
        conn = self.db.get_connection()
        try:
            conn.execute(
                "UPDATE SupportChats SET is_anonymous=0 WHERE id=?",
                (chat_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def get_all_active_chats(self) -> List[Dict]:
        """Все активные чаты (для психолога), отсортированные по последнему сообщению."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute('''
                SELECT sc.*,
                       (SELECT COUNT(*) FROM SupportMessages sm WHERE sm.chat_id = sc.id) AS msg_count,
                       (SELECT sm2.created_at FROM SupportMessages sm2 WHERE sm2.chat_id = sc.id
                        ORDER BY sm2.created_at DESC LIMIT 1) AS last_msg_at
                FROM SupportChats sc
                WHERE sc.status = 'active'
                ORDER BY last_msg_at DESC NULLS LAST
            ''').fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_all_closed_chats(self) -> List[Dict]:
        """Все закрытые чаты (для психолога)."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute('''
                SELECT sc.*,
                       (SELECT COUNT(*) FROM SupportMessages sm WHERE sm.chat_id = sc.id) AS msg_count
                FROM SupportChats sc
                WHERE sc.status = 'closed'
                ORDER BY sc.closed_at DESC
            ''').fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_student_chats(self, student_user_id: int) -> List[Dict]:
        """Все чаты студента (активный и история)."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute(
                "SELECT * FROM SupportChats WHERE student_user_id=? ORDER BY created_at DESC",
                (student_user_id,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Сообщения ──────────────────────────────────────────────────────────────

    def add_message(self, chat_id: int, sender_type: str, text: str) -> int:
        """
        Добавить сообщение в чат.
        sender_type: 'student' | 'psychologist'
        Возвращает ID сообщения.
        """
        conn = self.db.get_connection()
        try:
            cur = conn.execute(
                "INSERT INTO SupportMessages (chat_id, sender_type, text) VALUES (?,?,?)",
                (chat_id, sender_type, text),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def get_messages(self, chat_id: int, limit: int = 20) -> List[Dict]:
        """Получить последние N сообщений чата (в хронологическом порядке)."""
        conn = self.db.get_connection()
        try:
            rows = conn.execute('''
                SELECT * FROM (
                    SELECT * FROM SupportMessages WHERE chat_id=?
                    ORDER BY created_at DESC LIMIT ?
                ) ORDER BY created_at ASC
            ''', (chat_id, limit)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()
