import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, Request
import asyncpg

TOKEN = os.getenv("BOT_TOKEN")  # Змінна середовища для токена
DATABASE_URL = os.getenv("DATABASE_URL")  # URL бази даних
WEBHOOK_PATH = f"/webhook/{TOKEN}"  # Унікальний шлях для вебхука
WEBHOOK_URL = "https://your-app-name.onrender.com" + WEBHOOK_PATH  # Замініть на URL Render

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

logging.basicConfig(level=logging.INFO)

ADMIN_PASSWORD = "123456"
admin_sessions = set()  # Для збереження активних адмінів

db = None  # Глобальна змінна для підключення до БД

async def connect_db():
    global db
    db = await asyncpg.connect(DATABASE_URL)
    logging.info("Підключено до бази даних!")

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    await connect_db()
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

@dp.message(commands=["add_news"])
async def add_news(message: types.Message):
    if message.from_user.id in admin_sessions:
        await message.answer("Введіть заголовок новини:")
        admin_sessions.add((message.from_user.id, "title"))
    else:
        await message.answer("У вас немає доступу до цієї команди.")

@dp.message(commands=["start"])
async def start(message: types.Message):
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", message.from_user.id)
    if user:
        await message.answer("Вітаю! Ви вже зареєстровані.")
    else:
        await message.answer("Введіть своє ім'я для реєстрації:")
        admin_sessions.add((message.from_user.id, "register_name"))

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    session = admin_sessions.get(user_id)
    if session == "register_name":
        admin_sessions[user_id] = message.text
        groups = await db.fetch("SELECT * FROM groups")
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for group in groups:
            keyboard.add(types.KeyboardButton(group["name"]))
        await message.answer("Оберіть свою групу:", reply_markup=keyboard)
        admin_sessions[user_id] = "register_group"
    elif session == "register_group":
        group = await db.fetchrow("SELECT id FROM groups WHERE name=$1", message.text)
        if group:
            await db.execute("INSERT INTO students (user_id, name, group_id) VALUES ($1, $2, $3)", user_id, admin_sessions[user_id], group["id"])
            del admin_sessions[user_id]
            await message.answer("Реєстрація завершена! Тепер ви можете отримувати розклад і новини коледжа!😎.")
        else:
            await message.answer("Такої групи не існує. Спробуйте ще раз.🥲")
    elif user_id in admin_sessions:
        if message.text == ADMIN_PASSWORD:
            await message.answer("Ви увійшли в адмін-панель!👀 Доступні команди: /add_group, /del_group, /add_teacher, /del_teacher, /add_schedule, /del_schedule, /add_news")
        else:
            await message.answer("Невірний пароль!🥲")
            admin_sessions.remove(user_id)
    else:
        await message.answer("Привіт! я твій бот-помічник по коледжу!😘")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
