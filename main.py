import asyncio
import logging
import sys
from dotenv import load_dotenv
from os import getenv

from aiogram import F
from aiogram.utils.keyboard import InlineKeyboardMarkup
from aiogram.types.inline_keyboard_button import InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram import Bot, Dispatcher, html
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from data_manage import *
from utils import *

load_dotenv()

TOKEN = getenv('BOT_TOKEN')
ADMINS = getenv('ADMIN_ID').split(',')
teacher_queue = []

dp = Dispatcher()

class Form(StatesGroup):
    inactive = State()
    active = State()

@dp.message(CommandStart())
async def command_start(message: Message, state: FSMContext):
    await state.set_state(Form.inactive)
    id = message.from_user.id
    print(message.from_user.username)
    print(id)
    check = get_user(id) #(True, 'МАРИЯ ВАЛЕРЬЕВНА')
    if check and check[-1]==False:
        text = get_greeting(id)
        await message.answer(text)
    elif check and check[-1]:
        text = get_greeting(id, message.from_user.username)
        await message.answer(text)
    else:
        markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Я ученик👶🏿', callback_data='student')],
                                                       [InlineKeyboardButton(text='Я преподаватель🧑🏿‍🦽', callback_data='teacher')]])
        await message.answer(f'Привет, что-то не узнал тебя...', reply_markup=markup)
        
@dp.callback_query()
async def choose_role(query: CallbackQuery, bot: Bot, state: FSMContext):
    if query.data == 'student':
        await query.answer('Молоко на губах не обсохло')
        await bot.edit_message_text('Напиши свое ФИО, лицеист!', chat_id=query.message.chat.id, message_id=query.message.message_id)
        await state.set_state(Form.active)
    elif query.data == 'teacher':
        teacher_queue.append(query.from_user.id)
        await query.answer('Хаха плесень хайпует')
        await bot.edit_message_text('Напишите, пожалуйста, ваше ФИО', chat_id=query.message.chat.id, message_id=query.message.message_id)
        await state.set_state(Form.active)

@dp.message(F.text)
async def get_fi(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == Form.active:
        text = message.text
        text = text.split(' ')
        text.reverse()
        name = ' '.join(text)
        name = name.lower().title()
        id = message.from_user.id   

        print(teacher_queue)
        
        if name.count(' ') == 0:
            markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Я ученик👶🏿', callback_data='student')],
                                                       [InlineKeyboardButton(text='Я преподаватель🧑🏿‍🦽', callback_data='teacher')]])
            await message.answer(f'Что-то не похоже на имя', reply_markup=markup)

        elif message.from_user.id in teacher_queue:
            if message.from_user.username:
                if get_teacher(message.from_user.username):
                    reg_user(name, id, True)
                    text = get_greeting(id, message.from_user.username)
                    await message.answer(text)
                    
            else:
                teacher_queue.pop(-1)
                await message.answer(f'Вы отсутствуете в списках учителей. Если это ошибка, обратитесь в администрацию')

        else:
            if check_new_name(name):
                if check_existing_name(name):
                    await message.answer('Пользователь уже существует')
                else:
                    reg_user(name, id, isTeacher = False)
                    text = get_greeting(id)
                    await message.answer(text)
            else:
                markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Я ученик👶🏿', callback_data='student')],
                                                       [InlineKeyboardButton(text='Я преподаватель🧑🏿‍🦽', callback_data='teacher')]])
                await message.answer(f'Вас нет в списках проверьте фио или обратитесь в администрацию', reply_markup=markup)
    await state.clear()


async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())