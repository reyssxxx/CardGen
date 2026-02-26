import asyncio
import logging
import sys
from dotenv import load_dotenv
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from database.db_manager import init_db
from handlers import student_handlers, admin_handlers, common_handlers, teacher_handlers
from services.scheduler_service import SchedulerService

load_dotenv()

TOKEN = getenv('BOT_TOKEN')

dp = Dispatcher()

# Порядок роутеров важен: common → admin → teacher → student
dp.include_router(common_handlers.router)
dp.include_router(admin_handlers.router)
dp.include_router(teacher_handlers.router)
dp.include_router(student_handlers.router)


async def main():
    print("[INFO] Initializing database...")
    init_db()

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    scheduler = SchedulerService(bot)
    scheduler.start()
    print("[INFO] Scheduler started")

    try:
        print("[INFO] Bot started. Waiting for updates...")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\n[INFO] Bot stopped")
    except Exception as e:
        print(f"[ERROR] Bot crashed: {e}")
    finally:
        scheduler.stop()
        await bot.session.close()
        print("[INFO] Shutdown complete")


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, stream=sys.stdout)
    asyncio.run(main())