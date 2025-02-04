import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, Request

TOKEN = os.getenv("BOT_TOKEN")  # Змінна середовища для токена
WEBHOOK_PATH = f"/webhook/{TOKEN}"  # Унікальний шлях для вебхука
WEBHOOK_URL = "https://kofuka-bk1t.onrender.com" + WEBHOOK_PATH  # Замініть на URL Render


bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

logging.basicConfig(level=logging.INFO)

ADMIN_PASSWORD = "123456"
admin_sessions = set()  # Для збереження активних адмінів

async def init_db():
    global db
    db = await asyncpg.connect(DATABASE_URL)
    await db.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL
        );
        CREATE TABLE IF NOT EXISTS teachers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            contact TEXT
        );
        CREATE TABLE IF NOT EXISTS schedule (
            id SERIAL PRIMARY KEY,
            group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
            teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
            subject TEXT NOT NULL,
            day_of_week TEXT NOT NULL CHECK (day_of_week IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),
            time TEXT NOT NULL
        );
    ''')
    logging.info("База даних ініціалізована!")

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    await init_db()
    logging.info("Webhook встановлено!")

@app.post(WEBHOOK_PATH)
async def webhook_handler(update: dict):
    telegram_update = Update.model_validate(update)
    await dp.feed_update(bot, telegram_update)
    return {"status": "ok"}

@dp.message(commands=["admin"])
async def admin_login(message: types.Message):
    await message.answer("Введіть пароль для входу в адмінку:")
    admin_sessions.add(message.from_user.id)

@dp.message()
async def handle_message(message: types.Message):
    if message.from_user.id in admin_sessions:
        if message.text == ADMIN_PASSWORD:
            await message.answer("Ви увійшли в адмін-панель! Доступні команди: /add_group, /del_group, /add_teacher, /del_teacher, /add_schedule, /del_schedule")
        else:
            await message.answer("Невірний пароль!")
            admin_sessions.remove(message.from_user.id)
    else:
        await message.answer("Привіт! Бот працює через вебхук!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
