"""
FSM States для различных процессов в боте
"""
from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации"""
    selecting_role = State()
    selecting_class = State()
    selecting_name = State()
    confirming = State()
    entering_admin_password = State()


class AdminGradeUpload(StatesGroup):
    """Состояния для загрузки оценок через Excel"""
    selecting_class = State()
    selecting_action = State()
    waiting_for_file = State()
    confirming = State()


class AdminCreateEvent(StatesGroup):
    """Состояния для создания дня мероприятий"""
    entering_title = State()
    entering_date = State()
    entering_description = State()
    managing = State()


class AdminAddSection(StatesGroup):
    """Состояния для добавления секции к мероприятию"""
    entering_title = State()
    entering_host = State()
    entering_time = State()
    selecting_capacity = State()
    entering_custom_capacity = State()
    entering_description = State()


class AdminSendAnnouncement(StatesGroup):
    """Состояния для отправки объявления"""
    selecting_audience = State()
    entering_text = State()
    confirming = State()


class AdminTicket(StatesGroup):
    """Состояния для работы администратора с тикетом"""
    in_thread = State()


class AdminSendCards(StatesGroup):
    """Состояния для рассылки табелей"""
    selecting_class = State()
    confirming = State()


class AdminGradeManagement(StatesGroup):
    """Состояния для управления оценками (удаление, редактирование)"""
    selecting_class = State()
    selecting_student = State()
    confirming_delete = State()
    entering_new_grade = State()


class StudentTicket(StatesGroup):
    """Состояния для обращений к администрации (тикеты)"""
    creating = State()
    in_thread = State()


class TeacherSendAnnouncement(StatesGroup):
    """Состояния для отправки объявления учителем"""
    selecting_class = State()
    entering_text = State()
    confirming = State()


class StudentSupport(StatesGroup):
    """Состояния для анонимного чата с психологом (сторона ученика)"""
    in_chat = State()
    confirm_reveal = State()
    confirm_close = State()


class PsychologistChat(StatesGroup):
    """Состояния для работы психолога с чатом поддержки"""
    in_chat = State()
