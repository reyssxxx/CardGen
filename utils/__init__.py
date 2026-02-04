"""
Utils package - утилиты и вспомогательные функции
"""
from .validators import (
    validate_full_name,
    validate_grade,
    validate_date,
    validate_username,
    validate_class_name,
    validate_subject,
    normalize_full_name,
    parse_date_with_year,
    sanitize_filename
)

from .formatters import (
    format_date,
    format_grades_list,
    calculate_average,
    format_grade_with_average,
    format_student_grades_report,
    format_statistics,
    format_class_statistics,
    format_teacher_reminder,
    format_new_grades_notification,
    format_journal_status,
    escape_html,
    truncate_text
)

from .config_loader import (
    ConfigLoader,
    get_config,
    get_subjects,
    get_teachers,
    get_students_by_class,
    check_student_exists,
    get_teacher_by_username
)

from .greetings import get_greeting

__all__ = [
    # validators
    'validate_full_name',
    'validate_grade',
    'validate_date',
    'validate_username',
    'validate_class_name',
    'validate_subject',
    'normalize_full_name',
    'parse_date_with_year',
    'sanitize_filename',

    # formatters
    'format_date',
    'format_grades_list',
    'calculate_average',
    'format_grade_with_average',
    'format_student_grades_report',
    'format_statistics',
    'format_class_statistics',
    'format_teacher_reminder',
    'format_new_grades_notification',
    'format_journal_status',
    'escape_html',
    'truncate_text',

    # config_loader
    'ConfigLoader',
    'get_config',
    'get_subjects',
    'get_teachers',
    'get_students_by_class',
    'check_student_exists',
    'get_teacher_by_username',

    # greetings
    'get_greeting',
]
