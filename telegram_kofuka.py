import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI
import asyncpg

# Ініціалізація бота та FastAPI
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

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
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    buttons = [
        KeyboardButton("Мій розклад"),
        KeyboardButton("Контакти викладачів"),
        KeyboardButton("Учні у групах")
    ]
    keyboard.add(*buttons)
    await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=keyboard)

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

@dp.message(Command("Учні у групах"))
async def show_students_in_groups(message: types.Message):
    db = await connect_db()
    groups = await db.fetch("SELECT id, name FROM groups")
    response = "Учні у групах:\n"
    for group in groups:
        students = await db.fetch("SELECT name FROM students WHERE group_id=$1", group["id"])
        response += f"\n{group['name']}:\n"
        if students:
            response += "\n".join([student['name'] for student in students]) + "\n"
        else:
            response += "Немає студентів у цій групі.\n"
    await message.answer(response)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
