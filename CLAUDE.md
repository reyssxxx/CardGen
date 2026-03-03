# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CardGen is a Telegram bot for a Russian lyceum (ЮФУ) that manages grade distribution and student notifications. Admins upload grades via Excel, the bot generates personalized grade cards as images, and sends them to students on a bi-weekly schedule.

**Stack**: aiogram 3.x, SQLite, Playwright (HTML→PNG), APScheduler, openpyxl

## Running the Bot

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```

## Configuration

**`.env`** (required):
```
BOT_TOKEN=your_bot_token
ADMIN_ID=123456789,987654321
```

**`data/teachers.json`** — maps Telegram user ID (string) to teacher data:
```json
{
  "8306032588": {
    "name": "Иванова Анна Петровна",
    "subjects": ["Математика", "Физика"],
    "classes": ["11Т", "11Г"]
  }
}
```

**`data/students.json`** — maps class name to list of student full names:
```json
{ "11Т": ["Иванов Иван", "Петрова Мария"] }
```

**`data/config.json`** — list of subjects used for grade cards and Excel templates:
```json
{ "subjects": ["Математика", "Физика", ...] }
```
> The `teachers` array that may appear in this file is **legacy and unused** — teacher data is now in `teachers.json`.

**`data/psychologists.json`** — maps Telegram user ID (string) to psychologist data:
```json
{ "123456789": { "name": "Сидорова Елена Ивановна" } }
```

## Authentication & Role Detection

On `/start`, the bot checks in order:

1. **Admin**: Is `user_id` in `ADMIN_ID` env var? → Auto-register in DB, show admin menu
2. **Teacher**: Is `user_id` a key in `data/teachers.json`? → Auto-register in DB, show teacher menu
3. **Psychologist**: Is `user_id` a key in `data/psychologists.json`? → Show psychologist menu (NOT stored in DB)
4. **Registered student**: Is user in DB? → Show student menu
5. **New user**: Show registration keyboard (student only)

Student registration: select class → select name from `students.json` → confirm → inserted into DB.

## Router Priority (main.py)

Routers are included in this order — the order matters for handler filtering:
1. `common_handlers` — `/start`, `/cancel`, registration FSM
2. `admin_handlers` — grade uploads, grade cards, events, announcements, Q&A
3. `teacher_handlers` — announcement to class
4. `psychologist_handlers` — support chat management (psychologist side)
5. `student_support_handlers` — anonymous support chat (student side)
6. `student_handlers` — view grades, events, questions to admin

## Database

**Location**: `data/database.db` (auto-initialized on first run)

```sql
Users(ID PK, ФИ, class, isAdmin, isTeacher)
Grades(id PK, student_name, class, subject, grade, date, uploaded_by, created_at)
Events(id, title, description, date, time_slots JSON, class_limit, created_by, is_active, published)
EventSections(id, event_id FK, title, host, time, description, capacity, sort_order)
EventRegistrations(id, event_id FK, user_id, time_slot, student_name, class, section_id FK, registered_at)
Announcements(id, text, target, created_by, created_at, photo_file_id)
AnonQuestions(id, text, created_at, answered, answer, asker_user_id, photo_file_id, answer_photo_file_id)
SupportChats(id, student_user_id, is_anonymous, status, created_at, closed_at)
SupportMessages(id, chat_id FK, sender_type, text, created_at)
```

`grade` values: `'2'`, `'3'`, `'4'`, `'5'`, `'н'` (absent), `'б'` (sick).
`date` format: `DD.MM.YYYY`.

If the DB schema is wrong or stale: delete `data/database.db` and restart — it reinitializes automatically. Admins and teachers re-register on the next `/start`.

## Key Workflows

### Admin: Grade Upload
State: `AdminGradeUpload`
1. Select class → Upload Excel file (or download template)
2. `excel_import_service.py` parses & validates (student names, dates, grade values)
3. Preview parsed grades → Confirm → Bulk insert via `GradeRepository.add_grades_bulk()`

**Excel format** (`excel_import_service.py`):
- Row 1: `"Период:" | DD.MM.YYYY (start) | DD.MM.YYYY (end)` — period header
- Row 2: `"Предмет" | Student1 | Student2 | ...` — column headers
- Rows 3+: `Subject | grades | grades | ...` — multiple grades per cell, space-separated
- All grades linked to the period start date.

### Admin: Send Grade Cards
State: `AdminSendCards`
1. Select class (or all students) → Confirm
2. `grade_card_service.generate_grade_card()` renders an HTML table via Playwright → PNG
3. `mailing_service.send_grade_cards()` sends PNGs to students' Telegram

### Scheduled Mailing
Every 2 weeks, Sunday 18:00 — `mailing_service.send_grade_cards_to_all()` runs automatically.

### Teacher: Announcements
State: `TeacherSendAnnouncement`
- Select class (from their `classes` in `teachers.json`) → Enter text or upload photo → Confirm → `mailing_service.send_text_to_users()`

### Admin: Events, Announcements, Q&A
- **Events**: Create with title, date, optional description; then add sections (секции) with title, host, time, capacity. Students browse and register via student menu.
- **Announcements**: Broadcast text or photo to all students or a specific class (with `photo_file_id` support).
- **Q&A**: Students submit anonymous questions (with optional photo); admin sees author (`asker_user_id`) and answers; answer is forwarded to the student.
- **Grade management** (`AdminGradeManagement`): Admin can view/delete grades per student.

### Psychologist / Support Chat
- Students open anonymous support chats (`SupportChats`), exchange messages (`SupportMessages`) with the psychologist.
- Student can optionally reveal identity during the chat.
- Psychologist sees active chats and responds; bot relays messages bidirectionally.

## Grade Card Generation (`services/grade_card_service.py`)

1. Fetches all grades for a student from DB
2. Calculates 2-week periods from Sept 1 to today
3. Generates an HTML table (subjects × periods) with per-subject averages
4. Playwright renders HTML → PNG, saved to `data/grade_cards/{student_name}.png`

## FSM States (`handlers/states.py`)

| State Class | Used In |
|---|---|
| `RegistrationStates` | Student registration |
| `AdminGradeUpload` | Excel grade import |
| `AdminCreateEvent` | Event day creation (title, date, desc, managing sections) |
| `AdminAddSection` | Adding section to event day |
| `AdminSendAnnouncement` | Admin announcements |
| `AdminAnswerQuestion` | Q&A answering |
| `AdminSendCards` | Bulk grade card sending |
| `AdminGradeManagement` | Viewing/deleting student grades |
| `StudentQuestion` | Question submission |
| `TeacherSendAnnouncement` | Teacher class announcements |
| `StudentSupport` | Anonymous support chat (student side) |
| `PsychologistChat` | Support chat (psychologist side) |

## Repository Pattern

All DB access goes through repositories in `database/`:

```python
from database.grade_repository import GradeRepository
repo = GradeRepository()
repo.add_grades_bulk([{"student_name": ..., "class": ..., "subject": ..., "grade": ..., "date": ..., "uploaded_by": ...}])
```

## Inline Keyboard Callback Convention

Callbacks encode action + context: `f"action_{param1}_{param2}"`.
Parsed by splitting on `_` after matching the prefix:

```python
@router.callback_query(lambda c: c.data.startswith("grade_confirm_"))
async def handler(callback):
    _, _, class_name = callback.data.split("_", 2)
```

## Russian Language Notes

- All user-facing text is Russian
- Student names: `Фамилия Имя` (Last First), stored as-is from `students.json`
- Class names use Cyrillic letters: `11Т`, `10Г`, `11СЭ`, etc.
