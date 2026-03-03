import asyncio
import logging
import sys
from dotenv import load_dotenv
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database.db_manager import init_db
from handlers import student_handlers, common_handlers, teacher_handlers
from handlers.admin import router as admin_handlers
from handlers import student_support_handlers, psychologist_handlers
from services.scheduler_service import SchedulerService

load_dotenv()

TOKEN = getenv('BOT_TOKEN')

dp = Dispatcher()

# Порядок роутеров важен: common → admin → teacher → psychologist → student/support
dp.include_router(common_handlers.router)
dp.include_router(admin_handlers)
dp.include_router(teacher_handlers.router)
dp.include_router(psychologist_handlers.router)
dp.include_router(student_support_handlers.router)
dp.include_router(student_handlers.router)

logger = logging.getLogger(__name__)


async def main():
    logger.info("Initializing database...")
    init_db()

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    scheduler = SchedulerService(bot)
    scheduler.start()
    logger.info("Scheduler started")

    try:
        logger.info("Bot started. Waiting for updates...")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by KeyboardInterrupt")
    except Exception as e:
        logger.exception("Bot crashed: %s", e)
    finally:
        scheduler.stop()
        await bot.session.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stdout,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    # Убираем лишний шум от сторонних библиотек
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    asyncio.run(main())
