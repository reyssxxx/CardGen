# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CardGen is a Telegram bot for a Russian school (lyceum) that automates grade distribution and student notifications. The bot processes photos of handwritten grade journals using OCR, allows teachers to verify/edit results, and automatically sends personalized grade cards to students every 2 weeks.

**Key Technologies**: aiogram 3.x, EasyOCR, OpenCV, SQLite, APScheduler

## Running the Bot

```bash
# Install dependencies (includes EasyOCR models - takes several minutes)
pip install -r requirements.txt

# Run the bot
python main.py

# Test OCR without running the bot
python test_ocr.py <path_to_journal_photo>
```

## Database

**Location**: `./data/database.db` (SQLite)

The database auto-initializes on first run via `database/db_manager.py`. Key tables:
- `Users`: Student and teacher registration (indexed by telegram ID)
- `Grades`: Individual grade entries with student_name, class, subject, grade, date
- `PhotoUploads`: Journal upload tracking with status (pending/processed/error)
- `ScheduledMailings`: Tracks bi-weekly mailing schedule

All database operations use repository pattern (`database/*_repository.py`).

## Configuration Files

**data/config.json**:
```json
{
  "subjects": ["Математика", "Физика", ...],
  "teachers": [
    ["telegram_username", "Subject", "Class (optional)"]
  ]
}
```

**data/students.json**:
```json
{
  "11Т": ["Иванов Иван", "Петрова Мария"],
  "10Г": [...]
}
```

**.env** (required):
```
BOT_TOKEN=your_bot_token
ADMIN_ID=123456789,987654321
```

## Architecture

### Handler Flow (aiogram routers)
Handlers are registered in `main.py` in priority order:
1. `common_handlers` - Registration, /start (applies to all users)
2. `teacher_handlers` - Photo upload, manual grading, messaging
3. `student_handlers` - View grades, get grade cards
4. `admin_handlers` - User management, reports

### FSM State Management
All multi-step workflows use aiogram FSM states defined in `handlers/states.py`:
- `RegistrationStates` - Student/teacher registration
- `TeacherPhotoUpload` - Full photo upload workflow (most complex)
- `TeacherSendMessage` - Class messaging
- `AdminManagement` - Admin operations
- `StudentGrades` - Grade viewing

### OCR Pipeline (services/)
The OCR process is split into specialized modules:

1. **image_processing.py**: Preprocessing (rotation correction, perspective transform, CLAHE, binarization)
2. **ocr_service.py**: Text extraction (class detection, date parsing, name extraction, grade recognition)
3. **ocr_pipeline.py**: Full pipeline orchestration with validation against student lists

When a teacher uploads a photo:
- Image is preprocessed to correct angle/perspective
- Text is extracted using EasyOCR (Russian language)
- Student names are fuzzy-matched against `students.json` using rapidfuzz
- Results are presented for verification via inline keyboards
- Teacher can edit any date or grade before final save
- Grades are bulk-inserted into DB

### Scheduled Tasks (services/scheduler_service.py)
APScheduler runs three cron jobs:
- **Grade cards**: Every 2 weeks, Sunday 18:00 - Generate and send personalized grade cards to all students
- **Teacher reminders**: Every Friday 16:00 - Remind teachers to upload journal photos
- **Admin reports**: Every Monday 09:00 - Send journal status report to admins

### Grade Card Generation (services/grade_generator.py)
Uses template overlay approach:
- Base template: `templates/grade_card_template.png`
- Fetches student grades from DB for specified period
- Overlays grades onto template at predefined coordinates
- Applies color coding (green=5, yellow=4, red=3/2, gray=absent)
- Calculates and displays semester average
- Output: `data/grade_cards/{student_name}.png`

## Key Workflows

### Teacher Photo Upload (/photo command)
This is the most complex workflow, using `TeacherPhotoUpload` states:

1. Teacher selects subject → `waiting_for_class`
2. Teacher selects class (or auto-detect) → `waiting_for_photo`
3. Photo uploaded → `processing_ocr` (OCR runs, 10-30 seconds)
4. Show detected dates → `reviewing_dates` (teacher can edit each date)
5. For each student, show grades → `reviewing_students` (teacher can edit)
6. Final confirmation → bulk insert to Grades table, delete photo

The UI uses inline keyboards with callbacks that encode state (e.g., `date_edit_0`, `grade_edit_1_2`).

### Authentication
- **Admin**: Checked via telegram ID against ADMIN_ID in .env
- **Teacher**: Must have telegram username matching entry in config.json teachers list
- **Student**: Name must exist in students.json (case-insensitive fuzzy match)

Users register once via /start, data stored in Users table with isTeacher boolean.

## Common Development Tasks

### Adding a New Subject
Edit `data/config.json` subjects array. If the subject needs to appear on grade cards, also update `SUBJECT_ORDER` in `services/grade_generator.py`.

### Modifying OCR Behavior
- Preprocessing: Edit `services/image_processing.py` (e.g., adjust CLAHE parameters, binarization threshold)
- Recognition: Edit `services/ocr_service.py` (e.g., grade validation patterns, name normalization)
- Full pipeline: Edit `services/ocr_pipeline.py` (e.g., validation logic, fuzzy matching threshold)

Test changes with: `python test_ocr.py <image_path>`

### Debugging OCR Issues
Set `save_debug_images=True` in `JournalOCRPipeline` initialization to save intermediate processing steps to disk.

### Changing Scheduled Task Times
Edit cron expressions in `services/scheduler_service.py`. Format: `CronTrigger(day_of_week='sun', hour=18, minute=0)`

## Important Code Patterns

### Repository Pattern
All database operations use repositories:
```python
from database.grade_repository import GradeRepository
repo = GradeRepository()
grades = repo.get_student_grades(student_name, start_date, end_date)
repo.bulk_insert_grades(grades_list)
```

### Inline Keyboard Callbacks
Callbacks encode action and context: `f"action_{param1}_{param2}"`
```python
# Creating callback
callback_data=f"grade_edit_{student_idx}_{date_idx}"

# Parsing callback
@router.callback_query(lambda c: c.data.startswith("grade_edit_"))
async def handle_grade_edit(callback: CallbackQuery):
    _, _, student_idx, date_idx = callback.data.split("_")
```

### FSM State Data Storage
Use `state.update_data()` and `state.get_data()` to persist data across handler transitions:
```python
await state.update_data(subject=subject, detected_dates=dates)
data = await state.get_data()
subject = data['subject']
```

## Russian Language Specifics

- All user-facing text is in Russian
- Student names use format "Фамилия Имя" (Last First)
- Date format: DD.MM.YYYY
- Grade values: "2", "3", "4", "5" (Russian grading scale), "н" (absent), "б" (sick)

## File Structure Notes

- `handlers/` - Telegram message/callback handlers (one file per role)
- `keyboards/` - Inline keyboard builders (one file per role)
- `services/` - Business logic (OCR, mailing, scheduling, grade generation)
- `database/` - Repository pattern for DB operations
- `utils/` - Validators, formatters, config loaders
- `data/` - Runtime data (DB, uploaded photos, generated cards, config files)
- `templates/` - Static templates for grade card generation

Utility scripts in root:
- `check_db.py` - Inspect database contents
- `delete_user.py` - Remove user by telegram ID
- `test_ocr.py` - Test OCR pipeline on image file
- `test_grade_generator.py` - Test grade card generation

## Known Limitations

- OCR struggles with poor lighting, extreme angles, and handwriting
- Teacher must manually verify all OCR results before saving
- Grade card template has fixed subject list - adding subjects requires template modification
- Bi-weekly schedule is hardcoded (every 2 weeks from epoch, not configurable start date)
