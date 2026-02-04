"""
Функции для генерации приветственных сообщений
"""
import os
from typing import Optional
from dotenv import load_dotenv

from database.user_repository import UserRepository
from utils.config_loader import get_teacher_by_username

# Загрузка ADMINS из .env
load_dotenv()
ADMINS = os.getenv('ADMIN_ID', '').split(',') if os.getenv('ADMIN_ID') else []


def get_greeting(user_id: int, username: Optional[str] = None) -> str:
    """
    Получить приветственное сообщение для пользователя

    Args:
        user_id: Telegram ID пользователя
        username: Username пользователя (для учителей)
        admins: Список ID администраторов

    Returns:
        Приветственное сообщение
    """
    user_repo = UserRepository()
    user = user_repo.get_user(user_id)

    if not user:
        return "Приветствую! Вы не зарегистрированы в системе."

    name, is_teacher = user
    name_parts = name.split()
    short_name = name_parts[-1] if name_parts else name

    # Проверка на администратора
    if ADMINS and str(user_id) in ADMINS:
        return (
            f"Здравствуйте, {short_name}.\n"
            f"Вы — администратор бота.\n\n"
            f"/admin — панель администратора\n"
            f"/journal_status — состояние журнала\n"
            f"/force_mailing — запустить рассылку табелей"
        )

    # Учитель (по БД флагу is_teacher)
    if is_teacher:
        # Дополнительная проверка: есть ли в config.json
        teacher_data = None
        if username:
            teacher_data = get_teacher_by_username(username)

        if teacher_data and len(teacher_data) > 1:
            subject = teacher_data[1]
            return (
                f"Здравствуйте, {short_name}.\n"
                f"Ваш предмет — {subject}.\n\n"
                f"/photo — загрузить фото журнала\n"
                f"/add_grade — добавить оценку вручную\n"
                f"/teacher_menu — главное меню"
            )
        else:
            # Учитель в БД, но нет в config.json (или нет username)
            return (
                f"Здравствуйте, {short_name}.\n"
                f"Вы зарегистрированы как учитель.\n\n"
                f"⚠️ Для полного доступа необходимо:\n"
                f"1. Установить username в Telegram\n"
                f"2. Быть добавленным администратором в список учителей\n\n"
                f"/photo — загрузить фото журнала"
            )

    # Ученик
    return (
        f"Здравствуй, {short_name}.\n\n"
        f"/getcard — получить табель текущей успеваемости\n"
        f"/grades — посмотреть оценки\n"
        f"/stats — статистика"
    )
