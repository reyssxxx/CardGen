"""
FSM States для различных процессов в боте
"""
from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации"""
    entering_name_student = State()   # Ввод ФИО ученика
    entering_name_teacher = State()   # Ввод ФИО учителя


class TeacherPhotoUpload(StatesGroup):
    """Состояния для процесса загрузки фото журнала"""
    waiting_for_subject = State()      # Ожидание выбора предмета
    waiting_for_class = State()        # Ожидание выбора класса
    waiting_for_photo = State()        # Ожидание фото
    processing_ocr = State()           # Обработка OCR
    reviewing_dates = State()          # Проверка дат
    editing_date = State()             # Редактирование конкретной даты
    reviewing_students = State()       # Проверка оценок учеников
    editing_grade = State()            # Редактирование оценки
    final_confirmation = State()       # Финальное подтверждение


class TeacherManualGrade(StatesGroup):
    """Состояния для ручного добавления оценки"""
    waiting_for_subject = State()
    waiting_for_class = State()
    waiting_for_student = State()
    waiting_for_grade = State()
    waiting_for_date = State()
    confirmation = State()


class TeacherEditGrade(StatesGroup):
    """Состояния для редактирования оценки"""
    waiting_for_subject = State()
    waiting_for_student = State()
    selecting_grade = State()
    waiting_for_new_value = State()
    confirmation = State()


class TeacherSendMessage(StatesGroup):
    """Состояния для отправки сообщения классу"""
    waiting_for_class = State()
    waiting_for_message = State()
    waiting_for_attachments = State()
    confirmation = State()


class AdminManagement(StatesGroup):
    """Состояния для администрирования"""
    # Управление учителями
    add_teacher_username = State()
    add_teacher_subject = State()
    add_teacher_class = State()

    # Управление учениками
    add_student_name = State()
    add_student_class = State()

    # Управление предметами
    add_subject_name = State()

    # Рассылка
    admin_send_selecting_audience = State()
    admin_send_message = State()
    admin_send_confirmation = State()

    # Загрузка расписания
    upload_schedule_file = State()


class StudentGrades(StatesGroup):
    """Состояния для просмотра оценок учеником"""
    selecting_period = State()    # Выбор периода для /grades
    selecting_subject = State()   # Фильтр по предмету
