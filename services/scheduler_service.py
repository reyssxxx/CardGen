"""
Сервис планировщика задач (автоматические рассылки табелей)
"""
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.mailing_service import MailingService


class SchedulerService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.mailing_service = MailingService(bot)

    def start(self):
        """Запуск планировщика."""
        print("[INFO] Starting scheduler...")

        # Рассылка табелей каждые 2 недели, воскресенье 18:00
        self.scheduler.add_job(
            self._safe_send_grade_cards,
            CronTrigger(day_of_week='sun', hour=18, minute=0, week='*/2'),
            id='grade_cards_mailing',
            name='Grade Cards Mailing'
        )
        print("[INFO] Scheduled: Grade cards mailing (every 2 weeks, Sun 18:00)")

        self.scheduler.start()
        print("[INFO] Scheduler started successfully")

    def stop(self):
        """Остановка планировщика (graceful shutdown)."""
        print("[INFO] Stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        print("[INFO] Scheduler stopped")

    async def trigger_manual_mailing(self):
        """Принудительная рассылка табелей (для админа)."""
        print("[INFO] Manual grade cards mailing triggered")
        await self._safe_send_grade_cards()

    async def _safe_send_grade_cards(self):
        """Безопасная обёртка для рассылки табелей."""
        try:
            print("[INFO] Executing scheduled task: send_grade_cards")
            await self.mailing_service.send_grade_cards_to_all()
            print("[INFO] Scheduled task completed: send_grade_cards")
        except Exception as e:
            print(f"[ERROR] Scheduled mailing failed: {e}")
            import traceback
            traceback.print_exc()
