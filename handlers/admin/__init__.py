"""
Admin handlers package.
Объединяет все роутеры администратора в один.
"""
from aiogram import Router

from handlers.admin import grade_handlers, event_handlers, misc_handlers, grade_mgmt_handlers

router = Router()
router.include_router(misc_handlers.router)       # admin_cancel должен быть первым
router.include_router(grade_handlers.router)
router.include_router(event_handlers.router)
router.include_router(grade_mgmt_handlers.router)
