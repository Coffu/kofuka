import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, Request
import asyncpg

TOKEN = os.getenv("BOT_TOKEN")  # Змінна середовища для токена
DATABASE_URL = os.getenv("DATABASE_URL")  # URL бази даних
WEBHOOK_PATH = f"/webhook/{TOKEN}"  # Унікальний шлях для вебхука
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Змінна середовища для вебхука

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

db_pool = None  # Глобальне підключення до БД

logging.basicConfig(level=logging.INFO)

ADMIN_PASSWORD = "123456"
admin_sessions = {}

async def connect_db():
    global db_pool
    if db_pool is None:
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return db_pool

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info(f"Webhook встановлено: {WEBHOOK_URL}")
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)

@app.on_event("shutdown")
async def on_shutdown():
    await bot.session.close()
    if db_pool is not None:
        await db_pool.close()

@app.post(WEBHOOK_PATH)
async def webhook_handler(update: dict):
    telegram_update = types.Update.model_validate(update)
    await dp.feed_update(bot, telegram_update)
    return {"status": "ok"}

@dp.message(Command("admin"))
async def admin_login(message: types.Message):
    admin_sessions[message.from_user.id] = "waiting_password"
    await message.answer("Введіть пароль для входу в адмінку:")

@dp.message()
async def check_admin_password(message: types.Message):
    if message.from_user.id in admin_sessions and admin_sessions[message.from_user.id] == "waiting_password":
        if message.text == ADMIN_PASSWORD:
            del admin_sessions[message.from_user.id]
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            buttons = [
                KeyboardButton("Додати групу"), KeyboardButton("Видалити групу"),
                KeyboardButton("Додати викладача"), KeyboardButton("Видалити викладача"),
                KeyboardButton("Додати розклад"), KeyboardButton("Видалити розклад"),
                KeyboardButton("Додати новину")
            ]
            keyboard.add(*buttons)
            await message.answer("Ви увійшли в адмін-панель!", reply_markup=keyboard)
        else:
            await message.answer("Невірний пароль!")

@dp.message(Command("start"))
async def start(message: types.Message):
    db = await connect_db()
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", message.from_user.id)
    if user:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        buttons = [KeyboardButton("Мій розклад"), KeyboardButton("Контакти викладачів"), KeyboardButton("Новини")]
        keyboard.add(*buttons)
        await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=keyboard)
    else:
        admin_sessions[message.from_user.id] = "register_name"
        await message.answer("Введіть своє ім'я для реєстрації:")

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    db = await connect_db()
    
    if user_id in admin_sessions and admin_sessions[user_id] == "register_name":
        admin_sessions[user_id] = message.text
        groups = await db.fetch("SELECT name FROM groups")
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for group in groups:
            keyboard.add(KeyboardButton(group["name"]))
        await message.answer("Оберіть свою групу:", reply_markup=keyboard)
    elif user_id in admin_sessions:
        group = await db.fetchrow("SELECT id FROM groups WHERE name=$1", message.text)
        if group:
            await db.execute("INSERT INTO students (user_id, name, group_id) VALUES ($1, $2, $3)", user_id, admin_sessions[user_id], group["id"])
            del admin_sessions[user_id]
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            buttons = [KeyboardButton("Мій розклад"), KeyboardButton("Контакти викладачів"), KeyboardButton("Новини")]
            keyboard.add(*buttons)
            await message.answer("Реєстрація завершена! Ось ваші опції:", reply_markup=keyboard)
        else:
            await message.answer("Такої групи не існує. Спробуйте ще раз.")
    else:
        await message.answer("Привіт! Бот працює через вебхук!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
