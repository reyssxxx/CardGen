"""
Сервис планировщика задач (автоматические рассылки табелей)
"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from services.mailing_service import MailingService

logger = logging.getLogger(__name__)

_MOSCOW_TZ = ZoneInfo('Europe/Moscow')


def _next_sunday_18() -> datetime:
    """Ближайшее воскресенье в 18:00 по Москве (не раньше, чем через 1 мин)."""
    now = datetime.now(_MOSCOW_TZ)
    days_to_sunday = (6 - now.weekday()) % 7
    candidate = now.replace(hour=18, minute=0, second=0, microsecond=0) + timedelta(days=days_to_sunday)
    if candidate <= now + timedelta(minutes=1):
        candidate += timedelta(weeks=1)
    return candidate


class SchedulerService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler(timezone=_MOSCOW_TZ)
        self.mailing_service = MailingService(bot)

    def start(self):
        """Запуск планировщика."""
        logger.info("Starting scheduler...")

        # Рассылка табелей каждые 2 недели, воскресенье 18:00 по Москве.
        # IntervalTrigger(weeks=2) с якорем на ближайшее воскресенье гарантирует
        # точное расписание, в отличие от CronTrigger(week='*/2') который привязан
        # к чётным ISO-неделям и может пропустить первый запуск.
        start_date = _next_sunday_18()
        self.scheduler.add_job(
            self._safe_send_grade_cards,
            IntervalTrigger(weeks=2, start_date=start_date, timezone=_MOSCOW_TZ),
            id='grade_cards_mailing',
            name='Grade Cards Mailing',
        )
        logger.info(
            "Scheduled: Grade cards mailing every 2 weeks, first run %s MSK",
            start_date.strftime("%d.%m.%Y %H:%M"),
        )

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
