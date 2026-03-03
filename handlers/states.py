"""
FSM States для различных процессов в боте
"""
from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния для процесса регистрации"""
    selecting_class = State()
    selecting_name = State()
    confirming = State()


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
    managing = State()  # экран управления днём (список секций)


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


class AdminAnswerQuestion(StatesGroup):
    """Состояния для ответа на вопрос ученика"""
    entering_answer = State()


class AdminSendCards(StatesGroup):
    """Состояния для рассылки табелей"""
    selecting_class = State()
    confirming = State()



class StudentQuestion(StatesGroup):
    """Состояния для отправки вопроса администрации"""
    entering_question = State()
    confirming = State()


class TeacherSendAnnouncement(StatesGroup):
    """Состояния для отправки объявления учителем"""
    selecting_class = State()
    entering_text = State()
    confirming = State()


