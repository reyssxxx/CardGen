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

# Пользователи с временными правами (сбрасываются при /start)
_ghost_admins: set[int] = set()


def ghost_grant(user_id: int) -> None:
    _ghost_admins.add(user_id)


def ghost_revoke(user_id: int) -> None:
    _ghost_admins.discard(user_id)


def is_admin(user_id: int) -> bool:
    return user_repo.is_admin(user_id) or user_id in _ghost_admins
