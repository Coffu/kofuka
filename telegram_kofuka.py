import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
import asyncpg
import asyncio
from flask import Flask
from threading import Thread

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")  # Змінна середовища для токена
DATABASE_URL = os.getenv("DATABASE_URL")  # URL бази даних
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)

logger.info(f"DATABASE_URL: {DATABASE_URL}")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db_pool = None  # Глобальне підключення до БД

async def connect_db():
    global db_pool
    if db_pool is None:
        logger.info("Підключення до бази даних...")
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return db_pool

async def delete_webhook():
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            logger.info(f"Видалення активного вебхука: {webhook_info.url}")
            await bot.delete_webhook()
    except Exception as e:
        logger.error(f"Помилка видалення вебхука: {e}")

# Створення головного меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мій розклад")],
        [KeyboardButton(text="Контакти викладачів")],
        [KeyboardButton(text="Учні у групі")]
    ],
    resize_keyboard=True
)

start_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Почати")]],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    db = await connect_db()
    user_id = message.from_user.id
    student = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)
    if student:
        await message.answer("Ви вже зареєстровані!", reply_markup=main_menu)
    else:
        await message.answer("Вітаю! Натисніть 'Почати' для реєстрації.", reply_markup=start_menu)

@dp.message(lambda message: message.text == "Почати")
async def start_registration(message: types.Message):
    await message.answer("Введіть своє ім'я та прізвище для реєстрації:")

@dp.message()
async def handle_registration(message: types.Message):
    try:
        user_id = message.from_user.id
        db = await connect_db()
        student = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)
        if student:
            await message.answer("Ви вже зареєстровані!", reply_markup=main_menu)
            return

        name_parts = message.text.split()
        if len(name_parts) < 2:
            await message.answer("Будь ласка, введіть ім'я та прізвище.")
            return

        full_name = " ".join(name_parts)
        await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, full_name)

        groups = await db.fetch("SELECT name FROM groups")
        if not groups:
            await message.answer("У системі немає доступних груп.")
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=group["name"])] for group in groups],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer("Оберіть свою групу:", reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Помилка обробки реєстрації: {e}")

@dp.message()
async def handle_group_selection(message: types.Message):
    try:
        user_id = message.from_user.id
        db = await connect_db()
        group = await db.fetchrow("SELECT * FROM groups WHERE name=$1", message.text)
        if not group:
            await message.answer("Такої групи не знайдено. Оберіть зі списку.")
            return

        await db.execute("UPDATE students SET group_id=$1 WHERE user_id=$2", group["id"], user_id)
        student = await db.fetchrow("SELECT name FROM students WHERE user_id=$1", user_id)
        await message.answer(f"Вітаю вас, {student['name']}! Тепер ви маєте доступ до меню.", reply_markup=main_menu)
    except Exception as e:
        logger.error(f"Помилка вибору групи: {e}")

@dp.message(lambda message: message.text == "Мій розклад")
async def show_schedule(message: types.Message):
    db = await connect_db()
    student = await db.fetchrow("SELECT group_id FROM students WHERE user_id=$1", message.from_user.id)
    schedule = await db.fetch("SELECT subject, time FROM schedule WHERE group_id=$1", student["group_id"])
    schedule_text = "\n".join([f"{row['time']} - {row['subject']}" for row in schedule])
    await message.answer(f"Ваш розклад:\n{schedule_text}")

async def main():
    await delete_webhook()
    await connect_db()
    await dp.start_polling(bot)

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

@app.route("/")
def index():
    return "Бот працює!"

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.run(main())
