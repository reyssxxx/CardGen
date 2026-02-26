"""
Сервис планировщика задач (автоматические рассылки табелей)
"""
import logging
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from services.mailing_service import MailingService

logger = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()
        self.mailing_service = MailingService(bot)

    def start(self):
        """Запуск планировщика."""
        logger.info("Starting scheduler...")

        # Рассылка табелей каждые 2 недели, воскресенье 18:00 по Москве
        self.scheduler.add_job(
            self._safe_send_grade_cards,
            CronTrigger(day_of_week='sun', hour=18, minute=0, week='*/2',
                        timezone='Europe/Moscow'),
            id='grade_cards_mailing',
            name='Grade Cards Mailing'
        )
        logger.info("Scheduled: Grade cards mailing (every 2 weeks, Sun 18:00 MSK)")

        self.scheduler.start()
        logger.info("Scheduler started successfully")

    def stop(self):
        """Остановка планировщика (graceful shutdown)."""
        logger.info("Stopping scheduler...")
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")

    async def trigger_manual_mailing(self):
        """Принудительная рассылка табелей (для админа)."""
        logger.info("Manual grade cards mailing triggered")
        await self._safe_send_grade_cards()

    async def _safe_send_grade_cards(self):
        """Безопасная обёртка для рассылки табелей."""
        try:
            logger.info("Executing scheduled task: send_grade_cards")
            sent, failed = await self.mailing_service.send_grade_cards_to_all()
            logger.info("Scheduled task completed: sent=%d, failed=%d", sent, failed)
        except Exception as e:
            logger.exception("Scheduled mailing failed: %s", e)
