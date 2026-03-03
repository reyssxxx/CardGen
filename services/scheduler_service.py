"""
Сервис планировщика задач (автоматические рассылки табелей, напоминания, деактивация событий)
"""
import logging
from datetime import datetime, timedelta, date as date_cls
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


def _next_9am() -> datetime:
    """Ближайшее 9:00 по Москве (не раньше, чем через 1 мин)."""
    now = datetime.now(_MOSCOW_TZ)
    candidate = now.replace(hour=9, minute=0, second=0, microsecond=0)
    if candidate <= now + timedelta(minutes=1):
        candidate += timedelta(days=1)
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
        cards_start = _next_sunday_18()
        self.scheduler.add_job(
            self._safe_send_grade_cards,
            IntervalTrigger(weeks=2, start_date=cards_start, timezone=_MOSCOW_TZ),
            id='grade_cards_mailing',
            name='Grade Cards Mailing',
        )
        logger.info(
            "Scheduled: Grade cards mailing every 2 weeks, first run %s MSK",
            cards_start.strftime("%d.%m.%Y %H:%M"),
        )

        # Ежедневные задачи в 9:00 МСК: напоминания о мероприятиях + деактивация прошедших
        daily_start = _next_9am()
        self.scheduler.add_job(
            self._safe_daily_tasks,
            IntervalTrigger(days=1, start_date=daily_start, timezone=_MOSCOW_TZ),
            id='daily_tasks',
            name='Daily Tasks',
        )
        logger.info(
            "Scheduled: Daily tasks (reminders + cleanup) at 09:00 MSK, first run %s",
            daily_start.strftime("%d.%m.%Y %H:%M"),
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

    async def _safe_daily_tasks(self):
        """Безопасная обёртка для ежедневных задач."""
        try:
            logger.info("Executing daily tasks")
            await self._send_event_reminders()
            await self._deactivate_expired_events()
            logger.info("Daily tasks completed")
        except Exception as e:
            logger.exception("Daily tasks failed: %s", e)

    async def _send_event_reminders(self):
        """Отправить напоминания участникам мероприятий, которые состоятся завтра."""
        from database.event_repository import EventRepository
        event_repo = EventRepository()

        tomorrow = (date_cls.today() + timedelta(days=1)).strftime("%d.%m.%Y")
        events = event_repo.get_events_for_date(tomorrow)

        if not events:
            return

        for event in events:
            user_ids = event_repo.get_registered_user_ids(event['id'])
            if not user_ids:
                continue
            text = (
                f"⏰ <b>Напоминание!</b>\n"
                f"Завтра состоится: <b>{event['title']}</b> ({event['date']})\n"
                f"Ты записан — не пропусти!"
            )
            sent = 0
            for uid in user_ids:
                try:
                    await self.bot.send_message(uid, text, parse_mode="HTML")
                    sent += 1
                except Exception:
                    pass
            logger.info(
                "Event reminder sent for '%s' (%s): %d/%d recipients",
                event['title'], event['date'], sent, len(user_ids),
            )

    async def _deactivate_expired_events(self):
        """Деактивировать активные мероприятия с прошедшей датой."""
        from database.event_repository import EventRepository
        event_repo = EventRepository()

        expired = event_repo.get_expired_active_events()
        for event in expired:
            event_repo.deactivate_event(event['id'])
            logger.info(
                "Auto-deactivated expired event: '%s' (%s)",
                event['title'], event['date'],
            )
