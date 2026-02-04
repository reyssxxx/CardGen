"""
Сервис планировщика задач (автоматические рассылки и уведомления)
"""
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from os import getenv

from services.mailing_service import MailingService
from services.notification_service import NotificationService


class SchedulerService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.mailing_service = MailingService(bot)
        self.notification_service = NotificationService(bot)

        # Получить список админов из переменных окружения
        admin_ids_str = getenv('ADMINS', '')
        self.admin_ids = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip().isdigit()]

    def start(self):
        """
        Запуск планировщика с добавлением всех задач
        """
        print("[INFO] Starting scheduler...")

        # Задача 1: Рассылка табелей (каждые 2 недели, воскресенье 18:00)
        self.scheduler.add_job(
            self._safe_send_grade_cards,
            CronTrigger(day_of_week='sun', hour=18, minute=0, week='*/2'),
            id='grade_cards_mailing',
            name='Grade Cards Mailing'
        )
        print("[INFO] Scheduled: Grade cards mailing (every 2 weeks, Sun 18:00)")

        # Задача 2: Напоминания учителям (каждую пятницу 16:00)
        self.scheduler.add_job(
            self._safe_teacher_reminders,
            CronTrigger(day_of_week='fri', hour=16, minute=0),
            id='teacher_reminders',
            name='Teacher Photo Reminders'
        )
        print("[INFO] Scheduled: Teacher reminders (every Friday 16:00)")

        # Задача 3: Отчет админу (каждый понедельник 9:00)
        self.scheduler.add_job(
            self._safe_admin_reports,
            CronTrigger(day_of_week='mon', hour=9, minute=0),
            id='admin_reports',
            name='Admin Journal Status Reports'
        )
        print("[INFO] Scheduled: Admin reports (every Monday 09:00)")

        # Запуск планировщика
        self.scheduler.start()
        print("[INFO] Scheduler started successfully")

    def stop(self):
        """
        Остановка планировщика (graceful shutdown)
        """
        print("[INFO] Stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        print("[INFO] Scheduler stopped")

    async def trigger_manual_mailing(self):
        """
        Принудительная рассылка табелей (для админа)
        Вызывается вручную через команду /force_mailing
        """
        print("[INFO] Manual grade cards mailing triggered")
        await self._safe_send_grade_cards()

    async def _safe_send_grade_cards(self):
        """
        Безопасная обёртка для рассылки табелей
        Перехватывает все исключения чтобы планировщик не упал
        """
        try:
            print("[INFO] Executing scheduled task: send_grade_cards_to_all")
            await self.mailing_service.send_grade_cards_to_all()
            print("[INFO] Scheduled task completed: send_grade_cards_to_all")

        except Exception as e:
            print(f"[ERROR] Scheduled mailing failed: {e}")
            import traceback
            traceback.print_exc()

    async def _safe_teacher_reminders(self):
        """
        Безопасная обёртка для напоминаний учителям
        """
        try:
            print("[INFO] Executing scheduled task: notify_teachers_photo_reminder")
            await self.notification_service.notify_teachers_photo_reminder()
            print("[INFO] Scheduled task completed: notify_teachers_photo_reminder")

        except Exception as e:
            print(f"[ERROR] Teacher reminders failed: {e}")
            import traceback
            traceback.print_exc()

    async def _safe_admin_reports(self):
        """
        Безопасная обёртка для отчетов админу
        """
        try:
            print("[INFO] Executing scheduled task: notify_admin_journal_status")
            await self.notification_service.notify_admin_journal_status(self.admin_ids)
            print("[INFO] Scheduled task completed: notify_admin_journal_status")

        except Exception as e:
            print(f"[ERROR] Admin reports failed: {e}")
            import traceback
            traceback.print_exc()
