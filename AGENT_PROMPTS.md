# Промпты для параллельных агентов

## Контекст проекта

CardGen - телеграм-бот для школы (Лицей ЮФУ), который:
- Распознает оценки с фотографий журналов через OCR (EasyOCR)
- Генерирует и рассылает табели успеваемости ученикам
- Поддерживает три роли: администратор, учитель, ученик

### Текущее состояние
✅ **Спринт 1 ЗАВЕРШЕН** (Этапы 1-4, 10):
- Инфраструктура: БД (SQLite), репозитории, утилиты
- OCR сервис: предобработка изображений, распознавание оценок, полный пайплайн
- Функционал учителя: загрузка фото журнала с редактированием результатов OCR

### Структура проекта
```
CardGen/
├── main.py                          # Точка входа (уже интегрирован teacher_handlers)
├── handlers/
│   ├── teacher_handlers.py          ✅ ГОТОВ
│   ├── states.py                    ✅ ГОТОВ
│   ├── student_handlers.py          ❌ TODO (Агент 1)
│   └── admin_handlers.py            ❌ TODO (Агент 2)
├── services/
│   ├── ocr_pipeline.py              ✅ ГОТОВ
│   ├── grade_generator.py           ❌ TODO (Агент 1)
│   ├── mailing_service.py           ❌ TODO (Агент 2)
│   ├── scheduler_service.py         ❌ TODO (Агент 2)
│   └── notification_service.py      ❌ TODO (Агент 2)
├── keyboards/
│   ├── teacher_keyboards.py         ✅ ГОТОВ
│   ├── student_keyboards.py         ❌ TODO (Агент 1)
│   └── admin_keyboards.py           ❌ TODO (Агент 2)
├── database/
│   ├── grade_repository.py          ✅ ГОТОВ (есть методы для статистики)
│   └── user_repository.py           ✅ ГОТОВ
├── utils/                           ✅ ВСЕ ГОТОВО
├── templates/
│   └── grade_card_template.png      ✅ ГОТОВ (красивый шаблон)
```

### Используемые технологии
- **Бот**: aiogram 3.22.0
- **БД**: SQLite (репозитории уже созданы)
- **OCR**: EasyOCR (уже интегрирован)
- **Изображения**: Pillow, OpenCV
- **Планировщик**: APScheduler (в requirements.txt)

---

## 🟦 АГЕНТ 1: Спринт 2 - Генерация табелей и функционал ученика

### Цель
Реализовать генерацию красивых табелей успеваемости и полный функционал для учеников.

### Задачи

#### Этап 5: Генерация табелей (`services/grade_generator.py`)

**Входные данные:**
- Шаблон: `templates/grade_card_template.png` (УЖЕ СУЩЕСТВУЕТ)
  - Красивый шаблон с 18 предметами
  - Колонки для дат и оценок
  - Поле для среднего балла за полугодие

**Что нужно реализовать:**

1. **Класс `GradeCardGenerator`** в `services/grade_generator.py`:
   ```python
   class GradeCardGenerator:
       def __init__(self, template_path='./templates/grade_card_template.png'):
           # Загрузка шаблона

       def generate_card(self, student_name: str, class_name: str,
                        period_start: date, period_end: date) -> str:
           """
           Генерирует табель для ученика за период

           Returns:
               Путь к сгенерированному изображению
           """
           # 1. Загрузить шаблон
           # 2. Получить оценки из БД (использовать grade_repository.get_student_grades)
           # 3. Сгруппировать по предметам
           # 4. Наложить текст на шаблон (Pillow)
           #    - ФИО ученика
           #    - Класс
           #    - Период (дата начала - дата конца)
           #    - Оценки по каждому предмету
           #    - Средний балл (использовать formatters.calculate_average)
           # 5. Сохранить в data/grade_cards/
           # 6. Вернуть путь
   ```

2. **Требования:**
   - Использовать русские шрифты (Arial или DejaVuSans)
   - Автоподгонка размера текста если не влезает
   - Цветовая индикация: 5 → зеленый, 2-3 → красный, 4 → желтый
   - Обработка пустых оценок (если предмета нет у ученика)

3. **Интеграция:**
   - Добавить в `services/__init__.py`
   - Создать удобную функцию `generate_student_card(student_name, days=14)`

#### Этап 6: Функционал ученика

**Что нужно реализовать:**

1. **`keyboards/student_keyboards.py`**:
   ```python
   - get_student_main_menu() → Reply клавиатура
   - get_period_selection_keyboard() → Inline (за неделю, 2 недели, месяц, полугодие)
   - get_subject_filter_keyboard(subjects) → Inline (список предметов + "Все")
   ```

2. **`handlers/student_handlers.py`**:

   **Команда `/getcard`** (получить табель):
   ```python
   @router.message(Command("getcard"))
   async def cmd_getcard(message: Message):
       # 1. Определить ученика по telegram ID
       # 2. Генерировать табель за последние 14 дней
       # 3. Отправить изображение в чат
   ```

   **Команда `/grades`** (текущие оценки текстом):
   ```python
   @router.message(Command("grades"))
   async def cmd_grades(message: Message):
       # 1. Получить оценки за текущий семестр
       # 2. Сгруппировать по предметам
       # 3. Форматировать красиво (использовать formatters.format_student_grades_report)
       # Пример вывода:
       # 📊 Твои оценки за 2 полугодие:
       #
       # Математика: 5, 5, 4, 5 (средний: 4.75)
       # Физика: 4, 5, 4 (средний: 4.33)
       # ...
   ```

   **Команда `/stats`** (статистика):
   ```python
   @router.message(Command("stats"))
   async def cmd_stats(message: Message):
       # 1. Собрать статистику:
       #    - Количество 5, 4, 3, 2
       #    - Средний балл по всем предметам
       #    - Топ-3 лучших предмета
       # 2. Можно текстовый график (например: ⭐⭐⭐⭐⭐)
       # 3. Форматировать (использовать formatters.format_statistics)
   ```

3. **Обновление FSM states** в `handlers/states.py`:
   ```python
   class StudentGrades(StatesGroup):
       selecting_period = State()    # Выбор периода для /grades
       selecting_subject = State()   # Фильтр по предмету
   ```

4. **Интеграция в `main.py`**:
   ```python
   from handlers import student_handlers
   dp.include_router(student_handlers.router)
   ```

### Важные файлы для чтения перед началом:
- `database/grade_repository.py` - методы get_student_grades, get_average_grade
- `utils/formatters.py` - функции форматирования
- `utils/validators.py` - валидация данных
- `templates/grade_card_template.png` - шаблон для генерации

### Критерии готовности:
- ✅ Ученик может получить табель командой `/getcard`
- ✅ Табель корректно отображает все оценки и средний балл
- ✅ `/grades` показывает текстовую версию оценок
- ✅ `/stats` показывает статистику
- ✅ Все интегрировано в main.py

---

## 🟩 АГЕНТ 2: Спринт 3 - Автоматизация и администрирование

### Цель
Реализовать автоматическую рассылку табелей, систему уведомлений и базовый функционал администратора.

### Задачи

#### Этап 7: Система рассылки и планировщик

**Что нужно реализовать:**

1. **`services/mailing_service.py`**:
   ```python
   class MailingService:
       def __init__(self, bot: Bot):
           self.bot = bot

       async def send_to_student(self, student_id: int, message: str,
                                file_path: Optional[str] = None):
           """Отправка сообщения/файла одному ученику"""

       async def send_to_class(self, class_name: str, message: str,
                              file_path: Optional[str] = None):
           """Массовая рассылка классу"""
           # 1. Получить всех учеников класса (user_repository)
           # 2. Отправить каждому с задержкой (anti-flood)
           # 3. Логировать успех/ошибки

       async def send_to_all_students(self, message: str,
                                     file_path: Optional[str] = None):
           """Рассылка всем ученикам"""

       async def send_grade_cards_to_all(self):
           """
           ГЛАВНАЯ ФУНКЦИЯ: Автоматическая рассылка табелей

           Логика:
           1. Получить всех учеников из БД
           2. Для каждого:
              - Генерировать табель за последние 14 дней
              - Отправить личным сообщением
           3. Логировать в PhotoUploads или отдельную таблицу
           4. Обновить ScheduledMailings.last_mailing_date
           """
   ```

2. **`services/scheduler_service.py`**:
   ```python
   from apscheduler.schedulers.asyncio import AsyncIOScheduler
   from apscheduler.triggers.cron import CronTrigger

   class SchedulerService:
       def __init__(self, bot: Bot):
           self.bot = bot
           self.scheduler = AsyncIOScheduler()
           self.mailing_service = MailingService(bot)

       def start(self):
           """Запуск планировщика"""
           # Добавить задачу: каждые 2 недели, воскресенье 18:00
           self.scheduler.add_job(
               self.mailing_service.send_grade_cards_to_all,
               CronTrigger(day_of_week='sun', hour=18, minute=0,
                          week='*/2'),  # Каждые 2 недели
               id='grade_cards_mailing'
           )

           self.scheduler.start()

       def stop(self):
           """Остановка планировщика"""
           self.scheduler.shutdown()

       async def trigger_manual_mailing(self):
           """Принудительная рассылка (для админа)"""
           await self.mailing_service.send_grade_cards_to_all()
   ```

3. **Интеграция в `main.py`**:
   ```python
   from services.scheduler_service import SchedulerService

   async def main():
       init_db()
       bot = Bot(...)

       # Запуск планировщика
       scheduler = SchedulerService(bot)
       scheduler.start()
       print("[INFO] Scheduler started: grade cards every 2 weeks")

       try:
           await dp.start_polling(bot)
       finally:
           scheduler.stop()
   ```

#### Этап 11: Система уведомлений

**Что нужно реализовать:**

1. **`services/notification_service.py`**:
   ```python
   class NotificationService:
       def __init__(self, bot: Bot):
           self.bot = bot

       async def notify_students_new_grades(self, student_ids: List[int],
                                           grades_info: List[Dict]):
           """
           Уведомления ученикам о новых оценках

           grades_info формат:
           [
               {'student_id': 123, 'subject': 'Математика',
                'date': '01.09.2026', 'grade': '5'},
               ...
           ]

           Группировать по ученикам и отправлять красивое сообщение
           (использовать formatters.format_new_grades_notification)
           """

       async def notify_teachers_photo_reminder(self):
           """
           Напоминание учителям о загрузке фото

           Логика:
           1. Проверить PhotoUploads: кто не загружал на этой неделе
           2. Получить список учителей (config_loader)
           3. Отправить напоминание каждому
           """

       async def notify_admin_journal_status(self, admin_ids: List[int]):
           """
           Отчет админу о загрузках за неделю

           Использовать formatters.format_journal_status
           """
   ```

2. **Интеграция в `scheduler_service.py`**:
   ```python
   # Добавить в start():

   # Напоминания учителям: каждую пятницу 16:00
   self.scheduler.add_job(
       self.notification_service.notify_teachers_photo_reminder,
       CronTrigger(day_of_week='fri', hour=16, minute=0),
       id='teacher_reminders'
   )

   # Отчет админу: каждый понедельник 9:00
   self.scheduler.add_job(
       lambda: self.notification_service.notify_admin_journal_status(admin_ids),
       CronTrigger(day_of_week='mon', hour=9, minute=0),
       id='admin_reports'
   )
   ```

3. **Интеграция в `teacher_handlers.py`**:
   ```python
   # В функции save_grades_to_db после сохранения:

   # Собрать информацию о новых оценках
   notification_data = []
   for grade_entry in grades_data:
       student = get_user_by_name(grade_entry['student_name'])
       if student:
           notification_data.append({
               'student_id': student['ID'],
               'subject': grade_entry['subject'],
               'date': grade_entry['date'],
               'grade': grade_entry['grade']
           })

   # Отправить уведомления
   notification_service = NotificationService(callback.bot)
   await notification_service.notify_students_new_grades(
       [n['student_id'] for n in notification_data],
       notification_data
   )
   ```

#### Этап 8 (базовый): Функционал администратора

**Что нужно реализовать (минимальный набор):**

1. **`keyboards/admin_keyboards.py`**:
   ```python
   - get_admin_main_menu() → Reply клавиатура с кнопками:
     * 📝 Управление учителями
     * 📝 Управление учениками
     * 📊 Просмотр успеваемости
     * 📸 Состояние журнала
     * 📢 Рассылка сообщений
     * 🔄 Принудительная рассылка табелей

   - get_admin_teachers_keyboard() → Inline (добавить, удалить, список)
   - get_admin_students_keyboard() → Inline (добавить, удалить, список по классам)
   ```

2. **`handlers/admin_handlers.py`** (базовый функционал):

   **Проверка прав админа** (middleware):
   ```python
   def is_admin(user_id: int) -> bool:
       # Проверка в ADMINS из .env
   ```

   **Команда `/admin`**:
   ```python
   @router.message(Command("admin"))
   async def cmd_admin(message: Message):
       if not is_admin(message.from_user.id):
           return

       await message.answer(
           "👨‍💼 Панель администратора",
           reply_markup=get_admin_main_menu()
       )
   ```

   **Команда `/journal_status`** (состояние журнала):
   ```python
   @router.message(Command("journal_status"))
   async def cmd_journal_status(message: Message):
       # 1. Получить загрузки за последнюю неделю (photo_repository)
       # 2. Форматировать (formatters.format_journal_status)
       # 3. Вывести таблицу: учитель | предмет | класс | дата
   ```

   **Команда `/force_mailing`** (принудительная рассылка):
   ```python
   @router.message(Command("force_mailing"))
   async def cmd_force_mailing(message: Message):
       if not is_admin(message.from_user.id):
           return

       await message.answer("⏳ Запускаю рассылку табелей...")

       # Запустить scheduler.trigger_manual_mailing()

       await message.answer("✅ Рассылка завершена")
   ```

   **Команда `/admin_send`** (массовая рассылка):
   ```python
   # FSM для ввода сообщения и выбора аудитории
   # Использовать MailingService
   ```

3. **Обновление FSM states**:
   ```python
   class AdminManagement(StatesGroup):
       admin_send_selecting_audience = State()
       admin_send_message = State()
       admin_send_confirmation = State()
   ```

4. **Интеграция в `main.py`**:
   ```python
   from handlers import admin_handlers
   dp.include_router(admin_handlers.router)
   ```

### Важные файлы для чтения перед началом:
- `database/photo_repository.py` - методы для отслеживания загрузок
- `database/user_repository.py` - получение пользователей
- `utils/formatters.py` - форматирование уведомлений
- `handlers/teacher_handlers.py` - пример интеграции уведомлений

### Критерии готовности:
- ✅ Автоматическая рассылка табелей каждые 2 недели (воскресенье 18:00)
- ✅ Уведомления ученикам о новых оценках (после сохранения учителем)
- ✅ Напоминания учителям о загрузке фото (пятница 16:00)
- ✅ Отчет админу о состоянии журнала (понедельник 9:00)
- ✅ Админ может принудительно запустить рассылку
- ✅ Админ видит статус загрузок журналов
- ✅ Админ может отправить массовое сообщение

---

## Общие требования для обоих агентов

### Стиль кода:
- Использовать async/await
- Docstrings для всех функций
- Type hints где возможно
- Обработка исключений (try/except)
- Логирование (print для INFO, WARNING, ERROR)

### Импорты:
```python
# Всегда проверяйте что модули уже созданы:
from database.grade_repository import GradeRepository
from database.user_repository import UserRepository
from utils.formatters import format_date, calculate_average, ...
from utils.validators import validate_date, validate_grade, ...
```

### Anti-flood для Telegram:
```python
import asyncio

# При массовой рассылке:
for user in users:
    await bot.send_message(...)
    await asyncio.sleep(0.05)  # 50ms задержка
```

### Тестирование:
- После реализации создать тестовый скрипт или обновить существующий
- Проверить на реальных данных из БД

---

## Координация между агентами

### Агент 1 → Агент 2:
После реализации `services/grade_generator.py`, Агент 2 может использовать его в `mailing_service.send_grade_cards_to_all()`

### Общие файлы (НЕ КОНФЛИКТУЮТ):
- `main.py` - каждый добавляет свой router
- `handlers/states.py` - каждый добавляет свои классы FSM
- `services/__init__.py` - каждый экспортирует свои модули

### Если возникнет конфликт:
Приоритет у Агента 1 (так как Агент 2 зависит от grade_generator)

---

## Примерный порядок работы

### Агент 1:
1. Создать `services/grade_generator.py` (использовать Pillow для наложения текста)
2. Протестировать генерацию на тестовых данных
3. Создать `keyboards/student_keyboards.py`
4. Создать `handlers/student_handlers.py` с командами /getcard, /grades, /stats
5. Интегрировать в main.py
6. Протестировать через бота

### Агент 2:
1. Создать `services/mailing_service.py` (базовые функции рассылки)
2. Создать `services/notification_service.py` (форматирование уведомлений)
3. Создать `services/scheduler_service.py` (APScheduler)
4. Интегрировать уведомления в `teacher_handlers.py`
5. Создать базовый `handlers/admin_handlers.py`
6. Создать `keyboards/admin_keyboards.py`
7. Интегрировать в main.py
8. Протестировать планировщик (изменить время на +1 минуту для теста)

---

## Финальная проверка

После завершения обоих спринтов должно работать:

✅ **Полный цикл для ученика:**
1. Учитель загружает фото → оценки в БД
2. Ученик получает уведомление о новых оценках
3. Ученик запрашивает табель `/getcard` → получает изображение
4. Каждые 2 недели автоматически приходит табель

✅ **Полный цикл для учителя:**
1. Напоминание в пятницу о загрузке фото
2. Загрузка фото → ученики получают уведомления

✅ **Полный цикл для админа:**
1. Отчет в понедельник о состоянии журнала
2. Может запустить рассылку вручную
3. Может отправить массовое сообщение

---

## Полезные ссылки на документацию

- **aiogram 3**: https://docs.aiogram.dev/en/latest/
- **Pillow**: https://pillow.readthedocs.io/
- **APScheduler**: https://apscheduler.readthedocs.io/
- **SQLite**: https://docs.python.org/3/library/sqlite3.html

Удачи! 🚀
