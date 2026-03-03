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
    """Состояния для создания мероприятия"""
    entering_title = State()
    entering_date = State()
    selecting_limit = State()
    entering_custom_limit = State()
    entering_description = State()
    confirming = State()


class AdminSendAnnouncement(StatesGroup):
    """Состояния для отправки объявления"""
    selecting_audience = State()
    entering_text = State()
    confirming = State()


class AdminAnswerQuestion(StatesGroup):
    """Состояния для ответа на анонимный вопрос"""
    entering_answer = State()


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


class StudentAnonQuestion(StatesGroup):
    """Состояния для отправки анонимного вопроса"""
    entering_question = State()
    confirming = State()


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
