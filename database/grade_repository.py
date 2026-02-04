"""
Репозиторий для работы с оценками
"""
import sqlite3
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from database.db_manager import DatabaseManager


class GradeRepository:
    def __init__(self, db_path='./data/database.db'):
        self.db_manager = DatabaseManager(db_path)

    def add_grade(self, student_name: str, class_name: str, subject: str,
                  grade: str, grade_date: str, teacher_username: str) -> int:
        """
        Добавить оценку
        Возвращает: ID добавленной записи
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO Grades (student_name, class, subject, grade, date, teacher_username)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (student_name, class_name, subject, grade, grade_date, teacher_username))

            conn.commit()
            return cursor.lastrowid

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def add_grades_bulk(self, grades_data: List[Dict]) -> int:
        """
        Массовое добавление оценок (после OCR)
        grades_data: список словарей с ключами: student_name, class, subject, grade, date, teacher_username
        Возвращает: количество добавленных записей
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.executemany('''
                INSERT INTO Grades (student_name, class, subject, grade, date, teacher_username)
                VALUES (:student_name, :class, :subject, :grade, :date, :teacher_username)
            ''', grades_data)

            conn.commit()
            return cursor.rowcount

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_student_grades(self, student_name: str,
                          subject: Optional[str] = None,
                          start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> List[Dict]:
        """
        Получить оценки ученика с фильтрацией
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            query = 'SELECT * FROM Grades WHERE student_name=?'
            params = [student_name]

            if subject:
                query += ' AND subject=?'
                params.append(subject)

            if start_date:
                query += ' AND date>=?'
                params.append(start_date)

            if end_date:
                query += ' AND date<=?'
                params.append(end_date)

            query += ' ORDER BY date DESC'

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_grades_by_class(self, class_name: str, subject: Optional[str] = None) -> List[Dict]:
        """
        Получить все оценки по классу
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            if subject:
                cursor.execute('''
                    SELECT * FROM Grades
                    WHERE class=? AND subject=?
                    ORDER BY student_name, date DESC
                ''', (class_name, subject))
            else:
                cursor.execute('''
                    SELECT * FROM Grades
                    WHERE class=?
                    ORDER BY student_name, subject, date DESC
                ''', (class_name,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_average_grade(self, student_name: str, subject: Optional[str] = None) -> Optional[float]:
        """
        Получить средний балл ученика по предмету или по всем предметам
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            # Преобразуем оценки: 5→5, 4→4, 3→3, 2→2, остальное пропускаем
            if subject:
                cursor.execute('''
                    SELECT AVG(CAST(grade AS REAL)) as avg_grade
                    FROM Grades
                    WHERE student_name=? AND subject=? AND grade IN ('2', '3', '4', '5')
                ''', (student_name, subject))
            else:
                cursor.execute('''
                    SELECT AVG(CAST(grade AS REAL)) as avg_grade
                    FROM Grades
                    WHERE student_name=? AND grade IN ('2', '3', '4', '5')
                ''', (student_name,))

            result = cursor.fetchone()
            return result['avg_grade'] if result['avg_grade'] else None

        finally:
            conn.close()

    def get_class_statistics(self, class_name: str) -> Dict:
        """
        Получить статистику по классу
        Возвращает: средний балл по классу, количество оценок и т.д.
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            # Средний балл класса
            cursor.execute('''
                SELECT AVG(CAST(grade AS REAL)) as avg_grade
                FROM Grades
                WHERE class=? AND grade IN ('2', '3', '4', '5')
            ''', (class_name,))
            avg_grade = cursor.fetchone()['avg_grade']

            # Количество оценок по типам
            cursor.execute('''
                SELECT grade, COUNT(*) as count
                FROM Grades
                WHERE class=? AND grade IN ('2', '3', '4', '5')
                GROUP BY grade
            ''', (class_name,))
            grade_counts = {row['grade']: row['count'] for row in cursor.fetchall()}

            return {
                'class': class_name,
                'average_grade': round(avg_grade, 2) if avg_grade else None,
                'grade_counts': grade_counts
            }

        finally:
            conn.close()

    def delete_grade(self, grade_id: int) -> bool:
        """
        Удалить оценку по ID
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('DELETE FROM Grades WHERE id=?', (grade_id,))
            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def update_grade(self, grade_id: int, new_grade: str) -> bool:
        """
        Изменить оценку
        """
        conn = self.db_manager.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                UPDATE Grades SET grade=? WHERE id=?
            ''', (new_grade, grade_id))

            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
