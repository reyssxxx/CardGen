"""
Хендлеры администратора: загрузка оценок и рассылка табелей.
"""
import hashlib
import os
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext

from handlers.admin.common import is_admin, user_repo, grade_repo
from handlers.states import AdminGradeUpload, AdminSendCards
from keyboards.admin_keyboards import (
    get_admin_main_menu,
    get_class_selection_keyboard,
    get_grade_upload_action_keyboard,
    get_grade_confirm_keyboard,
    get_send_cards_keyboard,
    get_send_cards_confirm_keyboard,
    get_cancel_keyboard,
)
from services.mailing_service import MailingService
from services.excel_import_service import parse_grades_excel, generate_template_excel
from utils.config_loader import get_all_classes, get_students_by_class, get_subjects

router = Router()


# ── Загрузка оценок ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:grades")
async def menu_grades(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    classes = get_all_classes()
    await state.set_state(AdminGradeUpload.selecting_class)
    await callback.message.edit_text(
        "Выбери класс для загрузки оценок:",
        reply_markup=get_class_selection_keyboard(classes, "grade_class"),
    )


@router.callback_query(AdminGradeUpload.selecting_class, F.data.startswith("grade_class:"))
async def grade_select_class(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    class_name = callback.data.split(":", 1)[1]
    await state.update_data(selected_class=class_name)
    await state.set_state(AdminGradeUpload.selecting_action)
    await callback.message.edit_text(
        f"Класс: <b>{class_name}</b>\n\nЧто делаем?",
        parse_mode="HTML",
        reply_markup=get_grade_upload_action_keyboard(),
    )


@router.callback_query(AdminGradeUpload.selecting_action, F.data == "grade_download_template")
async def download_template(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    class_name = data["selected_class"]
    students = get_students_by_class(class_name)
    subjects = get_subjects()
    xlsx_bytes = generate_template_excel(class_name, students, subjects)
    file = BufferedInputFile(xlsx_bytes, filename=f"шаблон_{class_name}.xlsx")
    await callback.message.answer_document(file, caption=f"Шаблон для класса {class_name}")
    await state.clear()
    await callback.message.edit_text("Главное меню:", reply_markup=get_admin_main_menu())


@router.callback_query(AdminGradeUpload.selecting_action, F.data == "grade_upload_file")
async def ask_for_excel_file(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminGradeUpload.waiting_for_file)
    await callback.message.edit_text(
        "Отправь .xlsx файл с оценками:",
        reply_markup=get_cancel_keyboard(),
    )


@router.message(AdminGradeUpload.waiting_for_file, F.document)
async def process_excel_file(message: Message, state: FSMContext, bot: Bot):
    doc = message.document
    if not doc.file_name.endswith(".xlsx"):
        await message.answer("Отправь файл формата .xlsx", reply_markup=get_cancel_keyboard())
        return
    data = await state.get_data()
    class_name = data["selected_class"]
    students = get_students_by_class(class_name)
    wait = await message.answer("Обрабатываю файл...")
    file_path = f"data/uploaded_grades/{class_name}_{doc.file_id}.xlsx"
    os.makedirs("data/uploaded_grades", exist_ok=True)
    await bot.download(doc, destination=file_path)

    # Проверяем хэш файла на дубль
    with open(file_path, 'rb') as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()
    if grade_repo.is_file_uploaded(file_hash):
        await wait.delete()
        os.remove(file_path)
        await message.answer(
            "⚠️ Этот файл уже был загружен ранее. Повторная загрузка не выполнена.",
            reply_markup=get_cancel_keyboard(),
        )
        return

    try:
        result = parse_grades_excel(file_path, class_name, students)
    except Exception as e:
        await wait.delete()
        await message.answer(f"Ошибка при обработке файла:\n{e}")
        return
    await state.update_data(parsed_result=result, file_path=file_path, file_hash=file_hash)
    await state.set_state(AdminGradeUpload.confirming)
    skipped_text = ""
    if result["skipped"]:
        skipped_names = ", ".join(result["skipped"][:5])
        more = f" и ещё {len(result['skipped']) - 5}" if len(result["skipped"]) > 5 else ""
        skipped_text = f"\n⚠️ Не найдены: {skipped_names}{more}"
    p_start = result["period_start"].strftime('%d.%m')
    p_end = result["period_end"].strftime('%d.%m.%Y')
    text = (
        f"✅ Файл обработан\n"
        f"Класс: <b>{class_name}</b> | Период: {p_start} — {p_end}\n"
        f"Оценок: <b>{result['count']}</b>"
        f"{skipped_text}\n\nСохранить?"
    )
    await wait.delete()
    await message.answer(text, parse_mode="HTML", reply_markup=get_grade_confirm_keyboard())


@router.callback_query(AdminGradeUpload.confirming, F.data == "grade_confirm")
async def confirm_grades(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    result = data["parsed_result"]
    class_name = data.get("selected_class", "")
    inserted = grade_repo.bulk_insert_grades(result["grades"])
    file_hash = data.get("file_hash")
    if file_hash:
        grade_repo.save_file_hash(file_hash, class_name)
    await state.clear()
    await callback.message.edit_text(
        f"✅ Оценки сохранены: {inserted} записей.",
        reply_markup=get_admin_main_menu(),
    )

    if inserted == 0 or not class_name:
        return

    # Инвалидируем кэш и уведомляем учеников класса
    students = user_repo.get_students_by_class(class_name)
    for uid, name, _ in students:
        hash_file = f"./data/grade_cards/{name}.png.hash"
        if os.path.exists(hash_file):
            try:
                os.remove(hash_file)
            except OSError:
                pass
        try:
            await bot.send_message(
                uid,
                f"📊 Администратор загрузил новые оценки для класса <b>{class_name}</b>.\n"
                "Ты можешь посмотреть свой табель в главном меню.",
                parse_mode="HTML",
            )
        except Exception:
            pass


# ── Рассылка табелей ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "menu:send_cards")
async def menu_send_cards(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.answer()
    classes = get_all_classes()
    await state.set_state(AdminSendCards.selecting_class)
    await callback.message.edit_text(
        "Кому разослать табели?",
        reply_markup=get_send_cards_keyboard(classes),
    )


@router.callback_query(AdminSendCards.selecting_class, F.data.startswith("cards_class:"))
async def cards_select_class(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    target = callback.data.split(":", 1)[1]
    if target == "all":
        students = user_repo.get_all_students()
    else:
        students = user_repo.get_students_by_class(target)
    count = len(students)
    await state.update_data(cards_target=target, cards_count=count)
    await state.set_state(AdminSendCards.confirming)
    label = "всем" if target == "all" else f"классу {target}"
    await callback.message.edit_text(
        f"Разослать табели {label}: <b>{count}</b> учеников?",
        parse_mode="HTML",
        reply_markup=get_send_cards_confirm_keyboard(target, count),
    )


@router.callback_query(AdminSendCards.confirming, F.data.startswith("cards_confirm:"))
async def confirm_send_cards(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    data = await state.get_data()
    target = data["cards_target"]
    await state.clear()
    all_s = user_repo.get_all_students()
    students = all_s if target == "all" else [(uid, name, cls) for uid, name, cls in all_s if cls == target]
    progress_msg = await callback.message.edit_text(f"Начинаю рассылку... 0/{len(students)}")
    last_update = [0]

    async def on_progress(done, total):
        if done - last_update[0] >= 5 or done == total:
            last_update[0] = done
            try:
                await progress_msg.edit_text(f"📤 Отправлено: {done}/{total}")
            except Exception:
                pass

    mailing = MailingService(bot)
    sent, failed = await mailing.send_grade_cards(students, on_progress)
    await progress_msg.edit_text(
        f"✅ Рассылка завершена.\nОтправлено: {sent}. Ошибок: {failed}.",
        reply_markup=get_admin_main_menu(),
    )
