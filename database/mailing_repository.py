"""
Репозиторий для работы с расписанием рассылок
"""
from datetime import datetime
from typing import Optional
from database.db_manager import DatabaseManager


class MailingRepository:
    def __init__(self, db_path='./data/database.db'):
        self.db_manager = DatabaseManager(db_path)

    def update_last_mailing(self, mailing_date: str) -> bool:
        """
        Обновить дату последней рассылки

        Args:
            mailing_date: дата рассылки в формате 'YYYY-MM-DD'

        Returns:
            True если успешно
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            # Обновляем первую (и единственную) запись
            cursor.execute('''
                UPDATE ScheduledMailings
                SET last_mailing_date=?, next_mailing_date=NULL
                WHERE id=1
            ''', (mailing_date,))

            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Failed to update last_mailing_date: {e}")
            raise e
        finally:
            conn.close()

    def get_last_mailing_date(self) -> Optional[str]:
        """
        Получить дату последней рассылки

        Returns:
            Дата в формате 'YYYY-MM-DD' или None
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT last_mailing_date FROM ScheduledMailings WHERE id=1
            ''')

            result = cursor.fetchone()
            return result['last_mailing_date'] if result else None

        finally:
            conn.close()

    def get_mailing_status(self) -> dict:
        """
        Получить полный статус расписания рассылок

        Returns:
            Словарь с информацией о рассылках
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                SELECT * FROM ScheduledMailings WHERE id=1
            ''')

            result = cursor.fetchone()
            if result:
                return {
                    'last_mailing_date': result['last_mailing_date'],
                    'next_mailing_date': result['next_mailing_date'],
                    'status': result['status']
                }
            return {}

        finally:
            conn.close()
