"""
Сервис для массовой рассылки сообщений и табелей успеваемости
"""
import asyncio
from datetime import date, datetime, timedelta
from typing import Optional
from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramBadRequest

from database.user_repository import UserRepository
from database.mailing_repository import MailingRepository
from utils.config_loader import get_students_by_class

# Попытка импортировать реальный GradeCardGenerator,
# если не удалось - используем mock
try:
    from services.grade_generator import GradeCardGenerator
except ImportError:
    from services.grade_generator_mock import MockGradeCardGenerator as GradeCardGenerator
    print("[WARNING] Using mock GradeCardGenerator - real generator not available yet")


class MailingService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.user_repo = UserRepository()
        self.mailing_repo = MailingRepository()
        self.grade_generator = GradeCardGenerator()

    async def send_to_student(self, student_id: int, message: str,
                              file_path: Optional[str] = None):
        """
        Отправка сообщения/файла одному ученику

        Args:
            student_id: telegram ID ученика
            message: текст сообщения
            file_path: путь к файлу (если нужно отправить фото)
        """
        try:
            if file_path:
                photo = FSInputFile(file_path)
                await self.bot.send_photo(student_id, photo, caption=message)
            else:
                await self.bot.send_message(student_id, message)

            print(f"[INFO] Message sent to student {student_id}")

        except TelegramBadRequest as e:
            if "blocked" in str(e).lower():
                print(f"[INFO] Bot blocked by student {student_id}, skipping")
            else:
                print(f"[ERROR] Failed to send message to student {student_id}: {e}")
                raise

        except Exception as e:
            print(f"[ERROR] Failed to send message to student {student_id}: {e}")
            raise

    async def send_to_class(self, class_name: str, message: str,
                           file_path: Optional[str] = None):
        """
        Массовая рассылка сообщения классу

        Args:
            class_name: название класса (например, "10Т")
            message: текст сообщения
            file_path: путь к файлу (если нужно отправить фото)
        """
        try:
            # Получить список учеников класса
            students = get_students_by_class(class_name)

            if not students:
                print(f"[WARNING] No students found for class {class_name}")
                return

            sent_count = 0
            failed_count = 0

            for student_name in students:
                try:
                    # Получить telegram_id ученика
                    student = self.user_repo.get_user_by_name(student_name)

                    if not student:
                        print(f"[WARNING] Student {student_name} not found in database, skipping")
                        failed_count += 1
                        continue

                    student_id = student['ID']

                    # Отправить сообщение
                    await self.send_to_student(student_id, message, file_path)
                    sent_count += 1

                    # Anti-flood: задержка 50ms между отправками
                    await asyncio.sleep(0.05)

                except Exception as e:
                    print(f"[ERROR] Failed to send to {student_name}: {e}")
                    failed_count += 1

            print(f"[INFO] Class {class_name} mailing complete: "
                  f"{sent_count} success, {failed_count} failed")

        except Exception as e:
            print(f"[ERROR] Failed to send to class {class_name}: {e}")
            import traceback
            traceback.print_exc()

    async def send_to_all_students(self, message: str, file_path: Optional[str] = None):
        """
        Рассылка всем ученикам

        Args:
            message: текст сообщения
            file_path: путь к файлу (если нужно отправить фото)
        """
        try:
            # Получить всех учеников
            students = self.user_repo.get_all_students()

            if not students:
                print("[WARNING] No students found in database")
                return

            sent_count = 0
            failed_count = 0

            for student_id, student_name in students:
                try:
                    await self.send_to_student(student_id, message, file_path)
                    sent_count += 1

                    # Anti-flood: задержка 50ms между отправками
                    await asyncio.sleep(0.05)

                except Exception as e:
                    print(f"[ERROR] Failed to send to {student_name} (ID: {student_id}): {e}")
                    failed_count += 1

            print(f"[INFO] Mailing to all students complete: "
                  f"{sent_count} success, {failed_count} failed")

        except Exception as e:
            print(f"[ERROR] Failed to send to all students: {e}")
            import traceback
            traceback.print_exc()

    async def send_grade_cards_to_all(self):
        """
        ГЛАВНАЯ ФУНКЦИЯ: Автоматическая рассылка табелей всем ученикам
        Генерирует табель за последние 14 дней для каждого ученика и отправляет
        """
        try:
            print("[INFO] Starting grade cards mailing...")

            # Получить всех учеников
            students = self.user_repo.get_all_students()

            if not students:
                print("[WARNING] No students found in database")
                return

            # Определить период (последние 14 дней)
            period_end = date.today()
            period_start = period_end - timedelta(days=14)

            sent_count = 0
            failed_count = 0
            skipped_count = 0

            for student_id, student_name in students:
                try:
                    # Получить класс ученика (из имени файла или из БД)
                    # Временно используем заглушку
                    class_name = "Unknown"  # TODO: добавить класс в таблицу Users

                    # Генерировать табель
                    print(f"[INFO] Generating grade card for {student_name}...")
                    card_path = self.grade_generator.generate_card(
                        student_name=student_name,
                        class_name=class_name,
                        period_start=period_start,
                        period_end=period_end
                    )

                    if not card_path:
                        print(f"[WARNING] No grade card generated for {student_name}, skipping")
                        skipped_count += 1
                        continue

                    # Отправить табель
                    message = f"📊 Твой табель успеваемости за последние 2 недели!\n\n" \
                             f"Период: {period_start.strftime('%d.%m.%Y')} - " \
                             f"{period_end.strftime('%d.%m.%Y')}"

                    await self.send_to_student(student_id, message, card_path)
                    sent_count += 1

                    # Anti-flood: задержка 50ms между отправками
                    await asyncio.sleep(0.05)

                except TelegramBadRequest as e:
                    if "blocked" in str(e).lower():
                        print(f"[INFO] Bot blocked by {student_name}, skipping")
                        skipped_count += 1
                    else:
                        print(f"[ERROR] Failed to send card to {student_name}: {e}")
                        failed_count += 1

                except Exception as e:
                    print(f"[ERROR] Failed to generate/send card for {student_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    failed_count += 1

            # Обновить дату последней рассылки
            today = datetime.now().strftime('%Y-%m-%d')
            self.mailing_repo.update_last_mailing(today)

            print(f"[INFO] Grade cards mailing complete!")
            print(f"[INFO] Results: {sent_count} sent, {skipped_count} skipped, "
                  f"{failed_count} failed")

        except Exception as e:
            print(f"[ERROR] Grade cards mailing failed: {e}")
            import traceback
            traceback.print_exc()
