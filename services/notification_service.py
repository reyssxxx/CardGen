"""
Сервис для отправки уведомлений пользователям
"""
from typing import List, Dict
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from database.user_repository import UserRepository
from database.photo_repository import PhotoRepository
from utils.formatters import (
    format_new_grades_notification,
    format_teacher_reminder,
    format_journal_status
)
from utils.config_loader import get_config


class NotificationService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.user_repo = UserRepository()
        self.photo_repo = PhotoRepository()

    async def notify_students_new_grades(self, grades_info: List[Dict]):
        """
        Уведомления ученикам о новых оценках

        Args:
            grades_info: список словарей с ключами student_name, subject, date, grade
                        [{'student_name': 'Иванов Иван', 'subject': 'Математика',
                          'date': '2026-02-03', 'grade': '5'}, ...]
        """
        if not grades_info:
            print("[INFO] No grades to notify about")
            return

        # Группируем оценки по ученикам
        students_grades = {}
        for grade_info in grades_info:
            student_name = grade_info['student_name']
            if student_name not in students_grades:
                students_grades[student_name] = []
            students_grades[student_name].append({
                'subject': grade_info['subject'],
                'date': grade_info['date'],
                'grade': grade_info['grade']
            })

        # Отправляем уведомления каждому ученику
        sent_count = 0
        failed_count = 0

        for student_name, grades in students_grades.items():
            try:
                # Получить telegram_id ученика
                student = self.user_repo.get_user_by_name(student_name)

                if not student:
                    print(f"[WARNING] Student {student_name} not found in database, skipping")
                    failed_count += 1
                    continue

                student_id = student['ID']

                # Форматировать уведомление
                message = format_new_grades_notification(student_name, grades)

                # Отправить
                await self.bot.send_message(student_id, message)
                sent_count += 1
                print(f"[INFO] Sent grade notification to {student_name} (ID: {student_id})")

            except TelegramBadRequest as e:
                if "blocked" in str(e).lower():
                    print(f"[INFO] Bot blocked by student {student_name}, skipping")
                else:
                    print(f"[ERROR] Failed to send notification to {student_name}: {e}")
                failed_count += 1

            except Exception as e:
                print(f"[ERROR] Failed to send notification to {student_name}: {e}")
                failed_count += 1

        print(f"[INFO] Grade notifications sent: {sent_count} success, {failed_count} failed")

    async def notify_teachers_photo_reminder(self):
        """
        Напоминание учителям о загрузке фото журнала
        Отправляется тем, кто не загружал фото за последние 7 дней
        """
        try:
            # Получить список всех учителей из конфига
            config = get_config()
            teachers = config.get('teachers', [])

            if not teachers:
                print("[WARNING] No teachers found in config")
                return

            # Получить username всех учителей
            teacher_usernames = [teacher[0] for teacher in teachers]  # teacher[0] = username

            # Проверить кто не загружал
            teachers_without_uploads = self.photo_repo.get_teachers_without_uploads(
                teacher_usernames, days=7
            )

            if not teachers_without_uploads:
                print("[INFO] All teachers uploaded photos this week")
                return

            # Отправить напоминания
            sent_count = 0
            failed_count = 0

            for teacher_username in teachers_without_uploads:
                try:
                    # Найти данные учителя в конфиге
                    teacher_data = next(
                        (t for t in teachers if t[0] == teacher_username),
                        None
                    )

                    if not teacher_data:
                        print(f"[WARNING] Teacher {teacher_username} not found in config")
                        failed_count += 1
                        continue

                    subject = teacher_data[1]  # teacher[1] = subject

                    # Получить telegram_id учителя по username
                    # Примечание: нужно найти ФИО учителя для поиска в БД
                    # Временно пропускаем, так как в Users нет связи с username
                    print(f"[WARNING] Cannot send reminder to {teacher_username}: "
                          f"no telegram_id mapping in database")
                    failed_count += 1

                except Exception as e:
                    print(f"[ERROR] Failed to send reminder to {teacher_username}: {e}")
                    failed_count += 1

            print(f"[INFO] Teacher reminders sent: {sent_count} success, {failed_count} failed")

        except Exception as e:
            print(f"[ERROR] Failed to send teacher reminders: {e}")
            import traceback
            traceback.print_exc()

    async def notify_admin_journal_status(self, admin_ids: List[int]):
        """
        Отчет админу о загрузках журналов за последнюю неделю

        Args:
            admin_ids: список telegram ID администраторов
        """
        try:
            # Получить загрузки за последнюю неделю
            uploads = self.photo_repo.get_all_recent_uploads(days=7)

            # Форматировать отчет
            message = format_journal_status(uploads)

            # Отправить каждому админу
            sent_count = 0
            failed_count = 0

            for admin_id in admin_ids:
                try:
                    await self.bot.send_message(admin_id, message)
                    sent_count += 1
                    print(f"[INFO] Sent journal status to admin {admin_id}")

                except TelegramBadRequest as e:
                    if "blocked" in str(e).lower():
                        print(f"[INFO] Bot blocked by admin {admin_id}, skipping")
                    else:
                        print(f"[ERROR] Failed to send status to admin {admin_id}: {e}")
                    failed_count += 1

                except Exception as e:
                    print(f"[ERROR] Failed to send status to admin {admin_id}: {e}")
                    failed_count += 1

            print(f"[INFO] Admin status reports sent: {sent_count} success, {failed_count} failed")

        except Exception as e:
            print(f"[ERROR] Failed to send admin journal status: {e}")
            import traceback
            traceback.print_exc()
