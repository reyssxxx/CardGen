"""
Handlers для управления оценками администратором:
просмотр, редактирование и удаление отдельных оценок.
"""
import os
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from handlers.admin.common import grade_repo, is_admin
from handlers.states import AdminGradeManagement
from keyboards.admin_keyboards import (
    get_cancel_keyboard,
    get_class_selection_keyboard,
    get_grade_mgmt_students_keyboard,
    get_grade_list_keyboard,
    get_grade_actions_keyboard,
    get_grade_delete_confirm_keyboard,
)
from utils.config_loader import get_all_classes

router = Router()

VALID_GRADES = {"2", "3", "4", "5", "н", "б"}


def _invalidate_grade_card_cache(student_name: str) -> None:
    """Удалить кэш-хэш файл табеля при изменении оценок."""
    hash_file = f"./data/grade_cards/{student_name}.png.hash"
    if os.path.exists(hash_file):
        try:
            os.remove(hash_file)
        except OSError:
            pass


# ── Вход в управление оценками ───────────────────────────────────────────────

@router.callback_query(F.data == "menu:grade_mgmt")
async def menu_grade_mgmt(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    classes = get_all_classes()
    if not classes:
        await callback.message.edit_text(
            "Нет доступных классов.",
            reply_markup=get_cancel_keyboard(),
        )
        return
    await state.set_state(AdminGradeManagement.selecting_class)
    await callback.message.edit_text(
        "🗑 <b>Управление оценками</b>\n\nВыбери класс:",
        parse_mode="HTML",
        reply_markup=get_class_selection_keyboard(classes, "grade_mgmt_class"),
    )


# ── Выбор ученика ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("grade_mgmt_class:"))
async def grade_mgmt_class(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    class_name = callback.data.split(":", 1)[1]
    grades = grade_repo.get_grades_by_class(class_name)
    if not grades:
        await callback.message.edit_text(
            f"По классу <b>{class_name}</b> оценок нет.",
            parse_mode="HTML",
            reply_markup=get_class_selection_keyboard(get_all_classes(), "grade_mgmt_class"),
        )
        return
    # Дедупликация и сортировка имён
    names = sorted({g["student_name"] for g in grades})
    await state.update_data(grade_mgmt_class=class_name)
    await state.set_state(AdminGradeManagement.selecting_student)
    await callback.message.edit_text(
        f"Класс <b>{class_name}</b> — выбери ученика:",
        parse_mode="HTML",
        reply_markup=get_grade_mgmt_students_keyboard(names, class_name),
    )


# ── Список оценок ученика ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("grade_mgmt_student:"))
async def grade_mgmt_student(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    # callback_data: grade_mgmt_student:{student_name}:{class_name}
    parts = callback.data.split(":", 2)
    student_name = parts[1]
    class_name = parts[2] if len(parts) > 2 else ""
    grades = grade_repo.get_student_grades(student_name)
    if not grades:
        await callback.message.edit_text(
            f"У <b>{student_name}</b> оценок нет.",
            parse_mode="HTML",
            reply_markup=get_grade_mgmt_students_keyboard([], class_name),
        )
        return
    await state.update_data(grade_mgmt_student=student_name, grade_mgmt_class=class_name)
    await callback.message.edit_text(
        f"Оценки <b>{student_name}</b> ({class_name})\nВыбери запись:",
        parse_mode="HTML",
        reply_markup=get_grade_list_keyboard(grades, student_name, class_name),
    )


# ── Просмотр конкретной оценки ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("grade_mgmt_view:"))
async def grade_mgmt_view(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    grade_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    student_name = data.get("grade_mgmt_student", "")
    class_name = data.get("grade_mgmt_class", "")

    # Получаем конкретную оценку
    all_grades = grade_repo.get_student_grades(student_name)
    grade = next((g for g in all_grades if g["id"] == grade_id), None)
    if not grade:
        await callback.message.edit_text("Запись не найдена.")
        return

    text = (
        f"<b>Оценка:</b> {grade['grade']}\n"
        f"<b>Предмет:</b> {grade['subject']}\n"
        f"<b>Дата:</b> {grade['date']}\n"
        f"<b>Ученик:</b> {grade['student_name']}"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_grade_actions_keyboard(grade_id, student_name, class_name),
    )


# ── Запрос подтверждения удаления ─────────────────────────────────────────────

@router.callback_query(F.data.startswith("grade_mgmt_del_ask:"))
async def grade_mgmt_del_ask(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    grade_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    student_name = data.get("grade_mgmt_student", "")
    class_name = data.get("grade_mgmt_class", "")

    all_grades = grade_repo.get_student_grades(student_name)
    grade = next((g for g in all_grades if g["id"] == grade_id), None)
    if not grade:
        await callback.message.edit_text("Запись не найдена.")
        return

    text = (
        f"Удалить оценку?\n\n"
        f"<b>{grade['grade']}</b> по {grade['subject']}"
        f" от {grade['date']}"
        f"\nУченик: {student_name}"
    )
    await state.set_state(AdminGradeManagement.confirming_delete)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_grade_delete_confirm_keyboard(grade_id, student_name, class_name),
    )


# ── Подтверждение удаления ────────────────────────────────────────────────────

@router.callback_query(AdminGradeManagement.confirming_delete, F.data.startswith("grade_mgmt_del_confirm:"))
async def grade_mgmt_del_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    grade_id = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    student_name = data.get("grade_mgmt_student", "")
    class_name = data.get("grade_mgmt_class", "")

    grade_repo.delete_grade(grade_id)
    _invalidate_grade_card_cache(student_name)

    # Возвращаемся к списку оценок ученика
    grades = grade_repo.get_student_grades(student_name)
    await state.set_state(AdminGradeManagement.selecting_student)
    if grades:
        await callback.message.edit_text(
            f"✅ Оценка удалена.\n\nОценки <b>{student_name}</b> ({class_name})\nВыбери запись:",
            parse_mode="HTML",
            reply_markup=get_grade_list_keyboard(grades, student_name, class_name),
        )
    else:
        await callback.message.edit_text(
            f"✅ Оценка удалена. У <b>{student_name}</b> больше нет оценок.\n\nВыбери другого ученика:",
            parse_mode="HTML",
            reply_markup=get_grade_mgmt_students_keyboard(
                sorted({g["student_name"] for g in grade_repo.get_grades_by_class(class_name)}),
                class_name,
            ),
        )


# ── Редактирование оценки ─────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("grade_mgmt_edit:"))
async def grade_mgmt_edit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    if not is_admin(callback.from_user.id):
        return
    grade_id = int(callback.data.split(":", 1)[1])
    await state.update_data(editing_grade_id=grade_id)
    await state.set_state(AdminGradeManagement.entering_new_grade)
    await callback.message.edit_text(
        "Введи новую оценку (2, 3, 4, 5, н, б):",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AdminGradeManagement.entering_new_grade)
async def grade_mgmt_save_new(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    new_grade = message.text.strip().lower() if message.text else ""
    if new_grade not in VALID_GRADES:
        await message.answer(
            "Недопустимое значение. Введи одно из: 2, 3, 4, 5, н, б",
            reply_markup=get_cancel_keyboard(),
        )
        return

    data = await state.get_data()
    grade_id = data.get("editing_grade_id")
    student_name = data.get("grade_mgmt_student", "")
    class_name = data.get("grade_mgmt_class", "")

    grade_repo.update_grade(grade_id, new_grade)
    _invalidate_grade_card_cache(student_name)

    grades = grade_repo.get_student_grades(student_name)
    await state.set_state(AdminGradeManagement.selecting_student)
    await message.answer(
        f"✅ Оценка изменена на <b>{new_grade}</b>.\n\nОценки <b>{student_name}</b> ({class_name}):",
        parse_mode="HTML",
        reply_markup=get_grade_list_keyboard(grades, student_name, class_name),
    )
