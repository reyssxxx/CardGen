"""
Сервис для массовой рассылки сообщений и табелей успеваемости.
"""
import asyncio
import logging
import os
from typing import Optional
from aiogram import Bot
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from database.user_repository import UserRepository
from services.grade_card_service import generate_grade_card

logger = logging.getLogger(__name__)


class MailingService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.user_repo = UserRepository()

    async def _send_one(self, user_id: int, text: str, file_path: Optional[str] = None,
                        photo_file_id: Optional[str] = None) -> bool:
        """Отправить одному пользователю. Возвращает True при успехе."""
        try:
            if photo_file_id:
                await self.bot.send_photo(user_id, photo_file_id, caption=text, parse_mode="HTML")
            elif file_path:
                photo = FSInputFile(file_path)
                await self.bot.send_photo(user_id, photo, caption=text, parse_mode="HTML")
            else:
                await self.bot.send_message(user_id, text, parse_mode="HTML")
            return True
        except TelegramForbiddenError:
            logger.debug("User %s blocked the bot", user_id)
            return False
        except Exception as e:
            logger.warning("Failed to send message to %s: %s", user_id, e)
            return False

    async def send_text_to_users(self, user_ids: list[tuple], text: str,
                                 photo_file_id: Optional[str] = None) -> tuple[int, int]:
        """
        Разослать текст (или фото с подписью) списку пользователей.
        user_ids: [(user_id, name), ...]
        photo_file_id: Telegram file_id фото (если нужно отправить с фото)
        Returns: (sent, failed)
        """
        sent = failed = 0
        for user_id, name in user_ids:
            ok = await self._send_one(user_id, text, photo_file_id=photo_file_id)
            if ok:
                sent += 1
            else:
                failed += 1
            await asyncio.sleep(0.05)
        return sent, failed

    async def send_grade_cards(self, students: list[tuple],
                               progress_callback=None) -> tuple[int, int]:
        """
        Разослать табели список учеников.
        students: [(user_id, name, class_name), ...]
        progress_callback: async callable(sent, total) для прогресса.
        Returns: (sent, failed)
        """
        sent = failed = 0
        total = len(students)
        for user_id, name, class_name in students:
            card_path = None
            try:
                card_path = await generate_grade_card(name, class_name)
                ok = await self._send_one(user_id, f"Табель успеваемости\n{name}", card_path)
                if ok:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning("Failed to generate/send card for %s: %s", name, e)
                failed += 1
            finally:
                if card_path and os.path.exists(card_path):
                    try:
                        os.remove(card_path)
                    except OSError:
                        pass
            if progress_callback:
                await progress_callback(sent + failed, total)
            await asyncio.sleep(0.05)
        return sent, failed

    async def send_grade_cards_to_all(self) -> tuple[int, int]:
        """Разослать табели всем зарегистрированным ученикам (для планировщика)."""
        students = self.user_repo.get_all_students()
        return await self.send_grade_cards(students)
