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

**`data/config.json`** — list of subjects (the `teachers` array inside is **legacy and ignored**):
```json
{ "subjects": ["Математика", "Физика", ...] }
```

## Authentication & Role Detection

On `/start`, the bot checks in order:

1. **Admin**: Is `user_id` in `ADMIN_ID` env var? → Auto-register, show admin menu
2. **Teacher**: Is `user_id` a key in `data/teachers.json`? → Auto-register, show teacher menu
3. **Registered student**: Is user in DB? → Show student menu
4. **New user**: Show registration keyboard (student only)

Student registration: select class → select name from `students.json` → confirm → inserted into DB.

## Router Priority (main.py)

Routers are included in this order — the order matters for handler filtering:
1. `common_handlers` — `/start`, `/cancel`, registration FSM
2. `admin_handlers` — grade uploads, grade cards, events, announcements, Q&A
3. `teacher_handlers` — announcement to class
4. `student_handlers` — view grades, events, anonymous questions

## Database

**Location**: `data/database.db` (auto-initialized on first run)

```sql
Users(ID PK, ФИ, class, isAdmin, isTeacher)
Grades(id PK, student_name, class, subject, grade, date, uploaded_by, created_at)
Events(id, title, description, date, time_slots JSON, class_limit, created_by, is_active)
EventRegistrations(id, event_id FK, user_id, time_slot, student_name, class, registered_at)
Announcements(id, text, target, created_by, created_at)
AnonQuestions(id, text, created_at, answered, answer)
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

**Excel format**: Row 1 = header (`Ученик | Предмет | DD.MM.YYYY | ...`), subsequent rows = data. Multiple grades per cell are space-separated.

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
- Events: Create with title, date, time slots, class limit; students register via student menu
- Announcements: Broadcast to all students or a specific class
- Anonymous Q&A: Students submit questions; admin sees and answers them; answer is broadcast

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
| `AdminCreateEvent` | Event creation |
| `AdminSendAnnouncement` | Admin announcements |
| `AdminAnswerQuestion` | Q&A answering |
| `AdminSendCards` | Bulk grade card sending |
| `StudentEventRegistration` | Event sign-up |
| `StudentAnonQuestion` | Question submission |
| `TeacherSendAnnouncement` | Teacher class announcements |

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
