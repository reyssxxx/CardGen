# Как использовать промпты для параллельных агентов

## Быстрый старт

### Запуск Агента 1 (Генерация табелей + функционал ученика)

1. Откройте новую сессию Claude Code
2. Скопируйте весь раздел **"🟦 АГЕНТ 1"** из `AGENT_PROMPTS.md`
3. Вставьте в чат и запустите

Агент 1 создаст:
- `services/grade_generator.py`
- `keyboards/student_keyboards.py`
- `handlers/student_handlers.py`

### Запуск Агента 2 (Автоматизация + администрирование)

1. Откройте новую сессию Claude Code (параллельно с Агентом 1)
2. Скопируйте весь раздел **"🟩 АГЕНТ 2"** из `AGENT_PROMPTS.md`
3. Вставьте в чат и запустите

Агент 2 создаст:
- `services/mailing_service.py`
- `services/scheduler_service.py`
- `services/notification_service.py`
- `keyboards/admin_keyboards.py`
- `handlers/admin_handlers.py`

---

## Важно!

### Текущее состояние проекта
✅ **Спринт 1 ЗАВЕРШЕН** - вся инфраструктура готова:
- База данных (SQLite) с таблицами и репозиториями
- OCR сервис (полный пайплайн)
- Функционал учителя (загрузка фото журналов)
- Утилиты (валидаторы, форматеры, загрузчик конфигов)

### Зависимость между агентами
⚠️ **Агент 2 зависит от Агента 1** в одном месте:
- `mailing_service.send_grade_cards_to_all()` использует `grade_generator.generate_card()`

**Решение**: Агент 2 должен подождать пока Агент 1 создаст `grade_generator.py`,
либо использовать заглушку (placeholder):

```python
# В mailing_service.py (временная заглушка):
async def send_grade_cards_to_all(self):
    # TODO: Ждем пока Агент 1 создаст grade_generator
    # from services.grade_generator import GradeCardGenerator
    # generator = GradeCardGenerator()

    # Пока отправляем текстовую версию:
    for student_id, student_name in students:
        message = f"Табель для {student_name} будет доступен позже"
        await self.send_to_student(student_id, message)
```

Потом Агент 2 вернется и доработает после завершения Агента 1.

---

## Координация

### Файлы, которые будут изменены ОБОИМИ агентами:

1. **`main.py`** - добавление роутеров:
   - Агент 1: `dp.include_router(student_handlers.router)`
   - Агент 2: `dp.include_router(admin_handlers.router)`

   **Как избежать конфликта**: Каждый агент добавляет только СВОЮ строку

2. **`handlers/states.py`** - добавление FSM классов:
   - Агент 1: `class StudentGrades(StatesGroup)`
   - Агент 2: `class AdminManagement(StatesGroup)`

   **Конфликтов не будет** - разные классы

3. **`services/__init__.py`** - экспорт сервисов:
   - Агент 1: экспорт `GradeCardGenerator`
   - Агент 2: экспорт `MailingService, SchedulerService, NotificationService`

   **Конфликтов не будет** - разные импорты

### Если возникнет конфликт слияния
Приоритет у **Агента 1**, так как Агент 2 зависит от его результата.

---

## Тестирование после завершения

### После Агента 1:
```bash
# Запустить бота
python main.py

# В Telegram (от имени ученика):
/start
/getcard      # Должен вернуть табель за 14 дней
/grades       # Текстовая версия оценок
/stats        # Статистика
```

### После Агента 2:
```bash
# Запустить бота
python main.py

# Проверить логи:
# [INFO] Scheduler started: grade cards every 2 weeks
```

**Проверка автоматической рассылки** (изменить время на тест):
```python
# В scheduler_service.py временно изменить:
CronTrigger(day_of_week='sun', hour=18, minute=0)
# на:
CronTrigger(minute='*/1')  # Каждую минуту для теста
```

### После ОБОИХ агентов:
Полный цикл:
1. Учитель загружает фото `/photo`
2. Ученики получают уведомления о новых оценках
3. Ученик запрашивает табель `/getcard`
4. Каждые 2 недели автоматически приходят табели
5. Админ видит статус `/journal_status`
6. Админ может запустить рассылку вручную `/force_mailing`

---

## Структура проекта после завершения

```
CardGen/
├── main.py                          ✅ (+ роутеры от обоих агентов)
│
├── handlers/
│   ├── teacher_handlers.py          ✅ ГОТОВ
│   ├── student_handlers.py          ← Агент 1
│   ├── admin_handlers.py            ← Агент 2
│   └── states.py                    ✅ (+ классы от обоих агентов)
│
├── services/
│   ├── ocr_pipeline.py              ✅ ГОТОВ
│   ├── grade_generator.py           ← Агент 1
│   ├── mailing_service.py           ← Агент 2
│   ├── scheduler_service.py         ← Агент 2
│   └── notification_service.py      ← Агент 2
│
├── keyboards/
│   ├── teacher_keyboards.py         ✅ ГОТОВ
│   ├── student_keyboards.py         ← Агент 1
│   └── admin_keyboards.py           ← Агент 2
│
├── database/                        ✅ ВСЕ ГОТОВО
├── utils/                           ✅ ВСЕ ГОТОВО
└── templates/                       ✅ ВСЕ ГОТОВО
```

---

## Что делать если что-то пошло не так

### Ошибка импорта
```python
ImportError: cannot import name 'xxx'
```

**Решение**: Проверить что модуль создан и экспортирован в `__init__.py`

### Конфликт в main.py
```
Both agents modified main.py
```

**Решение**: Вручную объединить изменения:
```python
# Должно быть:
dp.include_router(teacher_handlers.router)  # Уже есть
dp.include_router(student_handlers.router)  # От Агента 1
dp.include_router(admin_handlers.router)    # От Агента 2
```

### БД не инициализируется
```bash
python -c "from database.db_manager import init_db; init_db()"
```

### EasyOCR не установлен
```bash
pip install easyocr
```

---

## После завершения обоих агентов

Создайте итоговый отчет:
1. Что реализовано
2. Как протестировать каждую функцию
3. Известные ограничения
4. Следующие шаги (Спринт 4: полный админ-функционал, статистика)

---

## Контакты

При возникновении вопросов или конфликтов:
- Проверьте `AGENT_PROMPTS.md` - там подробное описание
- Проверьте `SETUP.md` - инструкция по настройке
- Проверьте существующий код в `database/`, `utils/` - примеры реализации

Удачи! 🚀
