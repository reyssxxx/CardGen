"""
⚠️ DEPRECATED - НЕ ИСПОЛЬЗОВАТЬ В НОВОМ КОДЕ!

Этот модуль устарел и будет удален в будущих версиях.

Используйте вместо него:
- database/user_repository.py → UserRepository
- database/grade_repository.py → GradeRepository
- utils/config_loader.py → get_teacher_by_username, check_student_exists
"""

import warnings
warnings.warn(
    "data_manage.py is deprecated. Use database/user_repository.py instead",
    DeprecationWarning,
    stacklevel=2
)

import sqlite3 as sql
import json

def get_user(id):
    db = sql.connect('./data/database.db')
    cur = db.cursor()

    cur.execute('SELECT ФИ, isTeacher FROM Users WHERE ID=?', (id,))
    user = cur.fetchone()

    db.commit()
    db.close()

    return user

def check_new_name(name: str):
    name = name.lower()

    with open('./data/students.json', 'r', encoding='utf-8') as file:
        students = json.load(file)

    for group in students.values():     
        for i in group:
            if name == i.lower():
                return True
    
def get_teacher(username: str):
    username = username.lower()

    with open('./data/config.json', 'r', encoding='utf-8') as file:
        config = json.load(file)
    
    teachers = config["teachers"]

    for teacher in teachers:
        if username == teacher[0].lower():
            return teacher
    
def reg_user(name: str, id: int, isTeacher: bool):
    db = sql.connect('./data/database.db')
    cur = db.cursor()

    cur.execute('INSERT INTO Users (ФИ, ID, isTeacher) VALUES (?, ?, ?)', (name, id, isTeacher))

    db.commit()
    db.close()

def check_existing_name(name: str):
    db = sql.connect('./data/database.db')
    cur = db.cursor()

    cur.execute('SELECT * FROM Users WHERE ФИ=?', (name,))
    user = cur.fetchone()

    db.commit()
    db.close()
    print(user)
    if not user:
        return False
    return True

