"""
Загрузчик конфигурационных файлов
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from functools import lru_cache


class ConfigLoader:
    def __init__(self, base_path='./data'):
        self.base_path = Path(base_path)
        self.config_file = self.base_path / 'config.json'
        self.students_file = self.base_path / 'students.json'
        self.teachers_file = self.base_path / 'teachers.json'
        self.psychologists_file = self.base_path / 'psychologists.json'

    @lru_cache(maxsize=1)
    def load_config(self) -> Dict:
        """
        Загрузить config.json с кешированием
        Содержит: subjects (список предметов), teachers (список учителей)
        """
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # Валидация структуры
            if 'subjects' not in config or 'teachers' not in config:
                raise ValueError("Config must contain 'subjects' and 'teachers' keys")

            return config

        except FileNotFoundError:
            print(f"⚠️  Файл {self.config_file} не найден")
            return {'subjects': [], 'teachers': []}
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга {self.config_file}: {e}")
            return {'subjects': [], 'teachers': []}

    @lru_cache(maxsize=1)
    def load_students(self) -> Dict[str, List[str]]:
        """
        Загрузить students.json с кешированием
        Структура: {"11Т": ["Иванов Иван", "Петров Петр"], ...}
        """
        try:
            with open(self.students_file, 'r', encoding='utf-8') as f:
                students = json.load(f)

            # Валидация: должен быть словарь
            if not isinstance(students, dict):
                raise ValueError("Students file must be a dictionary")

            return students

        except FileNotFoundError:
            print(f"⚠️  Файл {self.students_file} не найден")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга {self.students_file}: {e}")
            return {}

    def get_subjects(self) -> List[str]:
        """Получить список предметов"""
        config = self.load_config()
        return config.get('subjects', [])

    def get_teachers(self) -> List:
        """
        Получить список учителей
        Формат: [["username", "Предмет", "Класс (опционально)"], ...]
        """
        config = self.load_config()
        return config.get('teachers', [])

    def get_teacher_by_username(self, username: str) -> Optional[List]:
        """
        Найти учителя по username
        Возвращает: ["username", "Предмет", "Класс"] или None
        """
        username = username.lower()
        teachers = self.get_teachers()

        for teacher in teachers:
            if teacher[0].lower() == username:
                return teacher

        return None

    def get_teacher_subjects(self, username: str) -> List[str]:
        """
        Получить предметы учителя
        Возвращает список предметов
        """
        teacher = self.get_teacher_by_username(username)
        if teacher and len(teacher) > 1:
            # Возвращаем предмет (может быть несколько через запятую)
            return [s.strip() for s in teacher[1].split(',')]
        return []

    def get_teacher_class(self, username: str) -> Optional[str]:
        """
        Получить класс, где учитель - классный руководитель
        """
        teacher = self.get_teacher_by_username(username)
        if teacher and len(teacher) > 2:
            return teacher[2]
        return None

    @lru_cache(maxsize=1)
    def load_teachers(self) -> Dict[str, Dict]:
        """
        Загрузить teachers.json с кешированием.
        Структура: {"telegram_id": {"name": "...", "subjects": [...], "classes": [...]}, ...}
        """
        try:
            with open(self.teachers_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Teachers file must be a dictionary")
            return data
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга {self.teachers_file}: {e}")
            return {}

    def get_teacher_by_id(self, user_id: int) -> Optional[Dict]:
        """Получить данные учителя по Telegram ID. Возвращает dict или None."""
        teachers = self.load_teachers()
        return teachers.get(str(user_id))

    def is_teacher(self, user_id: int) -> bool:
        """Проверить, является ли пользователь учителем."""
        return self.get_teacher_by_id(user_id) is not None

    def get_teacher_classes(self, user_id: int) -> List[str]:
        """Получить список классов учителя."""
        teacher = self.get_teacher_by_id(user_id)
        if teacher:
            return teacher.get('classes', [])
        return []

    def get_teacher_subjects(self, user_id: int) -> List[str]:
        """Получить список предметов учителя по ID."""
        teacher = self.get_teacher_by_id(user_id)
        if teacher:
            return teacher.get('subjects', [])
        return []

    def get_teacher_name(self, user_id: int) -> Optional[str]:
        """Получить имя учителя по ID."""
        teacher = self.get_teacher_by_id(user_id)
        if teacher:
            return teacher.get('name')
        return None

    @lru_cache(maxsize=1)
    def load_psychologists(self) -> Dict[str, Dict]:
        """
        Загрузить psychologists.json с кешированием.
        Структура: {"telegram_id": {"name": "..."}, ...}
        """
        try:
            with open(self.psychologists_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Psychologists file must be a dictionary")
            return data
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга {self.psychologists_file}: {e}")
            return {}

    def is_psychologist(self, user_id: int) -> bool:
        """Проверить, является ли пользователь психологом."""
        return str(user_id) in self.load_psychologists()

    def get_psychologist_name(self, user_id: int) -> Optional[str]:
        """Получить имя психолога по Telegram ID."""
        data = self.load_psychologists().get(str(user_id))
        return data.get('name') if data else None

    def get_psychologist_user_id(self) -> Optional[int]:
        """Получить Telegram ID единственного психолога или None."""
        psychologists = self.load_psychologists()
        for uid_str in psychologists:
            try:
                return int(uid_str)
            except ValueError:
                pass
        return None

    def get_students_by_class(self, class_name: str) -> List[str]:
        """Получить список учеников по классу"""
        students = self.load_students()
        return students.get(class_name, [])

    def get_all_classes(self) -> List[str]:
        """Получить список всех классов"""
        students = self.load_students()
        return list(students.keys())

    def check_student_exists(self, name: str) -> bool:
        """
        Проверить существование ученика в списках
        """
        name = name.lower()
        students = self.load_students()

        for class_students in students.values():
            for student in class_students:
                if student.lower() == name:
                    return True

        return False

    def get_student_class(self, name: str) -> Optional[str]:
        """
        Найти класс ученика по ФИО
        """
        name = name.lower()
        students = self.load_students()

        for class_name, class_students in students.items():
            for student in class_students:
                if student.lower() == name:
                    return class_name

        return None

    def save_config(self, config: Dict) -> bool:
        """
        Сохранить config.json
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)

            # Очистить кеш
            self.load_config.cache_clear()
            return True

        except Exception as e:
            print(f"❌ Ошибка сохранения {self.config_file}: {e}")
            return False

    def save_students(self, students: Dict) -> bool:
        """
        Сохранить students.json
        """
        try:
            with open(self.students_file, 'w', encoding='utf-8') as f:
                json.dump(students, f, ensure_ascii=False, indent=4)

            # Очистить кеш
            self.load_students.cache_clear()
            return True

        except Exception as e:
            print(f"❌ Ошибка сохранения {self.students_file}: {e}")
            return False

    def add_subject(self, subject: str) -> bool:
        """Добавить предмет"""
        config = self.load_config()
        if subject not in config['subjects']:
            config['subjects'].append(subject)
            return self.save_config(config)
        return False

    def remove_subject(self, subject: str) -> bool:
        """Удалить предмет"""
        config = self.load_config()
        if subject in config['subjects']:
            config['subjects'].remove(subject)
            return self.save_config(config)
        return False

    def add_teacher(self, username: str, subject: str, class_name: Optional[str] = None) -> bool:
        """Добавить учителя"""
        config = self.load_config()
        teacher_data = [username, subject]
        if class_name:
            teacher_data.append(class_name)

        config['teachers'].append(teacher_data)
        return self.save_config(config)

    def remove_teacher(self, username: str) -> bool:
        """Удалить учителя"""
        config = self.load_config()
        teachers = config['teachers']
        config['teachers'] = [t for t in teachers if t[0].lower() != username.lower()]
        return self.save_config(config)


# Глобальный экземпляр
_config_loader = ConfigLoader()


# Удобные функции для быстрого доступа
def get_config() -> Dict:
    return _config_loader.load_config()


def get_subjects() -> List[str]:
    return _config_loader.get_subjects()


def get_teachers() -> List:
    return _config_loader.get_teachers()


def get_students_by_class(class_name: str) -> List[str]:
    return _config_loader.get_students_by_class(class_name)


def get_all_classes() -> List[str]:
    return _config_loader.get_all_classes()


def check_student_exists(name: str) -> bool:
    return _config_loader.check_student_exists(name)


def get_teacher_by_username(username: str) -> Optional[List]:
    return _config_loader.get_teacher_by_username(username)


def get_teacher_by_id(user_id: int) -> Optional[Dict]:
    return _config_loader.get_teacher_by_id(user_id)


def is_teacher(user_id: int) -> bool:
    return _config_loader.is_teacher(user_id)


def get_teacher_classes(user_id: int) -> List[str]:
    return _config_loader.get_teacher_classes(user_id)


def get_teacher_subjects_by_id(user_id: int) -> List[str]:
    return _config_loader.get_teacher_subjects(user_id)


def get_teacher_name(user_id: int) -> Optional[str]:
    return _config_loader.get_teacher_name(user_id)


def is_psychologist(user_id: int) -> bool:
    return _config_loader.is_psychologist(user_id)


def get_psychologist_name(user_id: int) -> Optional[str]:
    return _config_loader.get_psychologist_name(user_id)


def get_psychologist_user_id() -> Optional[int]:
    return _config_loader.get_psychologist_user_id()
