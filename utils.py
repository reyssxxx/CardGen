from data_manage import *
from main import ADMINS

def get_greeting(id: int, username=None):
    #здесь надо написать функцию которая будет возвращать приветственный текст с разными вариациями и командами (как в фигме)
    user = get_user(id)
    name = user[0].split()[-1]
    if str(id) in ADMINS:
        return f'Здравствуйте, {name}.\nВы — администратор бота.\n\nПидорович соси'
    elif user[-1]:
        subject = get_teacher(username)[1]
        return f'Здравствуйте, {name}.\nВаш предмет — {subject}.\n\n/photo — внести фотографию журнала'
    else:
        return f'Здравствуй, {name}.\n\n/getcard — получить табель текущей успеваемости'