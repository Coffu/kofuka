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

@dp.message(Command("start"))
async def start(message: types.Message):
    db = await connect_db()
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", message.from_user.id)
    if user:
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        buttons = [KeyboardButton("Мій розклад"), KeyboardButton("Контакти викладачів")]
        keyboard.add(*buttons)
        await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=keyboard)
    else:
        await message.answer("Введіть своє ім'я та прізвище для реєстрації:")

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    db = await connect_db()
    
    if len(message.text.split()) < 2:
        await message.answer("Будь ласка, введіть ім'я та прізвище.")
        return
    
    students = await db.fetch("SELECT user_id FROM students WHERE user_id=$1", user_id)
    if students:
        await message.answer("Ви вже зареєстровані!")
        return
    
    groups = await db.fetch("SELECT name FROM groups")
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for group in groups:
        keyboard.add(KeyboardButton(group["name"]))
    
    await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, message.text)
    await message.answer("Оберіть свою групу:", reply_markup=keyboard)

@dp.message()
async def choose_group(message: types.Message):
    user_id = message.from_user.id
    db = await connect_db()
    group = await db.fetchrow("SELECT id FROM groups WHERE name=$1", message.text)
    
    if group:
        await db.execute("UPDATE students SET group_id=$1 WHERE user_id=$2", group["id"], user_id)
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        buttons = [KeyboardButton("Мій розклад"), KeyboardButton("Контакти викладачів")]
        keyboard.add(*buttons)
        await message.answer("Реєстрація завершена! Ось ваші опції:", reply_markup=keyboard)
    else:
        await message.answer("Такої групи не існує. Спробуйте ще раз.")

@dp.message(Command("Контакти викладачів"))
async def show_teachers(message: types.Message):
    db = await connect_db()
    teachers = await db.fetch("SELECT name, subject, email FROM teachers")
    response = "Контакти викладачів:\n"
    for teacher in teachers:
        response += f"{teacher['name']} ({teacher['subject']}): {teacher['email']}\n"
    await message.answer(response)

@dp.message(Command("Мій розклад"))
async def show_schedule(message: types.Message):
    db = await connect_db()
    user = await db.fetchrow("SELECT group_id FROM students WHERE user_id=$1", message.from_user.id)
    if not user:
        await message.answer("Ви ще не зареєстровані!")
        return
    schedule = await db.fetch("SELECT subject, day, time, classroom FROM schedule WHERE group_id=$1", user["group_id"])
    response = "Ваш розклад:\n"
    for lesson in schedule:
        response += f"{lesson['day']} {lesson['time']} - {lesson['subject']} (Ауд. {lesson['classroom']})\n"
    await message.answer(response)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))

