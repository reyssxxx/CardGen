"""
Общие зависимости для admin-хендлеров.
"""
from database.user_repository import UserRepository
from database.grade_repository import GradeRepository
from database.event_repository import EventRepository
from database.announcement_repository import AnnouncementRepository
user_repo = UserRepository()
grade_repo = GradeRepository()
event_repo = EventRepository()
announce_repo = AnnouncementRepository()


def is_admin(user_id: int) -> bool:
    return user_repo.is_admin(user_id)
