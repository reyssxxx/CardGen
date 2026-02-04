"""
Репозиторий для работы с журналом загрузок фото
"""
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from database.db_manager import DatabaseManager


class PhotoRepository:
    def __init__(self, db_path='./data/database.db'):
        self.db_manager = DatabaseManager(db_path)

    def add_upload(self, teacher_username: str, subject: str,
                   class_name: str, file_path: Optional[str] = None) -> int:
        """
        Добавить запись о загрузке фото
        Возвращает: ID записи
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO PhotoUploads (teacher_username, subject, class, file_path, status)
                VALUES (?, ?, ?, ?, 'processing')
            ''', (teacher_username, subject, class_name, file_path))

            conn.commit()
            return cursor.lastrowid

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def update_status(self, upload_id: int, status: str,
                      error_message: Optional[str] = None) -> bool:
        """
        Обновить статус загрузки
        status: 'processing', 'processed', 'error'
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            if status == 'processed':
                cursor.execute('''
                    UPDATE PhotoUploads
                    SET status=?, processed_date=CURRENT_TIMESTAMP
                    WHERE id=?
                ''', (status, upload_id))
            else:
                cursor.execute('''
                    UPDATE PhotoUploads
                    SET status=?, error_message=?
                    WHERE id=?
                ''', (status, error_message, upload_id))

            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_teacher_uploads(self, teacher_username: str,
                           days: int = 7) -> List[Dict]:
        """
        Получить загрузки учителя за последние N дней
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                SELECT * FROM PhotoUploads
                WHERE teacher_username=? AND upload_date>=?
                ORDER BY upload_date DESC
            ''', (teacher_username, since_date))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_all_recent_uploads(self, days: int = 7) -> List[Dict]:
        """
        Получить все загрузки за последние N дней
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            cursor.execute('''
                SELECT * FROM PhotoUploads
                WHERE upload_date>=?
                ORDER BY upload_date DESC
            ''', (since_date,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_teachers_without_uploads(self, teachers_list: List[str],
                                     days: int = 7) -> List[str]:
        """
        Получить список учителей, которые не загружали фото за последние N дней
        teachers_list: список username учителей
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            since_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')

            placeholders = ','.join('?' * len(teachers_list))
            cursor.execute(f'''
                SELECT DISTINCT teacher_username FROM PhotoUploads
                WHERE teacher_username IN ({placeholders})
                AND upload_date>=?
            ''', teachers_list + [since_date])

            uploaded = {row['teacher_username'] for row in cursor.fetchall()}
            return [t for t in teachers_list if t not in uploaded]

        finally:
            conn.close()

    def get_upload_statistics(self) -> Dict:
        """
        Получить общую статистику загрузок
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            # Всего загрузок
            cursor.execute('SELECT COUNT(*) as total FROM PhotoUploads')
            total = cursor.fetchone()['total']

            # По статусам
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM PhotoUploads
                GROUP BY status
            ''')
            by_status = {row['status']: row['count'] for row in cursor.fetchall()}

            # За последнюю неделю
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                SELECT COUNT(*) as week_count
                FROM PhotoUploads
                WHERE upload_date>=?
            ''', (week_ago,))
            week_count = cursor.fetchone()['week_count']

            return {
                'total_uploads': total,
                'by_status': by_status,
                'last_week': week_count
            }

        finally:
            conn.close()
