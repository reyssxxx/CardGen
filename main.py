import asyncio
import logging
import sys
from dotenv import load_dotenv
from os import getenv

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# Импорт новых компонентов
from database.db_manager import init_db
from handlers import teacher_handlers, student_handlers, admin_handlers, common_handlers
from services.scheduler_service import SchedulerService

load_dotenv()

TOKEN = getenv('BOT_TOKEN')

dp = Dispatcher()

# Подключение роутеров (ВАЖНО: порядок имеет значение!)
dp.include_router(common_handlers.router)  # Сначала общие (start, регистрация)
dp.include_router(teacher_handlers.router)
dp.include_router(student_handlers.router)
dp.include_router(admin_handlers.router)


async def main():
    # Инициализация базы данных
    print("[INFO] Initializing database...")
    init_db()
    print("[INFO] Database initialized successfully")

    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # Запуск планировщика
    scheduler = SchedulerService(bot)
    scheduler.start()
    print("[INFO] Scheduler started: grade cards every 2 weeks (Sun 18:00)")
    print("[INFO] Teacher reminders: every Friday 16:00")
    print("[INFO] Admin reports: every Monday 09:00")

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.stop()
        print("[INFO] Scheduler stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())