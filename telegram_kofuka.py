import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
import asyncpg
import asyncio
from flask import Flask

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")  # Змінна середовища для токена
DATABASE_URL = os.getenv("DATABASE_URL")  # URL бази даних
PORT = int(os.getenv("PORT", 5000))

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Flask додаток
app = Flask(__name__)

@app.route('/')
def index():
    return "Бот працює!"

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

@dp.message(Command("start"))
async def start(message: types.Message):
    try:
        logger.info(f"Користувач {message.from_user.id} виконав команду /start")
        db = await connect_db()
        user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", message.from_user.id)
        if user:
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            buttons = [KeyboardButton("Мій розклад"), KeyboardButton("Контакти викладачів"), KeyboardButton("Учні у групі")]
            keyboard.add(*buttons)
            await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=keyboard)
        else:
            await message.answer("Введіть своє ім'я та прізвище для реєстрації:")
    except Exception as e:
        logger.error(f"Помилка в обробці команди /start: {e}")

@dp.message()
async def handle_message(message: types.Message):
    try:
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
    except Exception as e:
        logger.error(f"Помилка обробки повідомлення: {e}")

@dp.message()
async def choose_group(message: types.Message):
    try:
        user_id = message.from_user.id
        db = await connect_db()
        group = await db.fetchrow("SELECT id FROM groups WHERE name=$1", message.text)

        if group:
            await db.execute("UPDATE students SET group_id=$1 WHERE user_id=$2", group["id"], user_id)
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            buttons = [KeyboardButton("Мій розклад"), KeyboardButton("Контакти викладачів"), KeyboardButton("Учні у групі")]
            keyboard.add(*buttons)
            await message.answer("Реєстрація завершена! Ось ваші опції:", reply_markup=keyboard)
        else:
            await message.answer("Такої групи не існує. Спробуйте ще раз.")
    except Exception as e:
        logger.error(f"Помилка обробки вибору групи: {e}")

@dp.message(Command("Контакти викладачів"))
async def show_teachers(message: types.Message):
    try:
        db = await connect_db()
        teachers = await db.fetch("SELECT name, subject, email FROM teachers")
        response = "Контакти викладачів:\n"
        for teacher in teachers:
            response += f"{teacher['name']} ({teacher['subject']}): {teacher['email']}\n"
        await message.answer(response)
    except Exception as e:
        logger.error(f"Помилка виведення контактів викладачів: {e}")

@dp.message(Command("Мій розклад"))
async def show_schedule(message: types.Message):
    try:
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
    except Exception as e:
        logger.error(f"Помилка виведення розкладу: {e}")

@dp.message(Command("Учні у групі"))
async def show_students_in_group(message: types.Message):
    try:
        db = await connect_db()
        user = await db.fetchrow("SELECT group_id FROM students WHERE user_id=$1", message.from_user.id)
        if not user:
            await message.answer("Ви ще не зареєстровані!")
            return
        students = await db.fetch("SELECT name FROM students WHERE group_id=$1", user["group_id"])
        response = "Учні у вашій групі:\n"
        for student in students:
            response += f"{student['name']}\n"
        await message.answer(response)
    except Exception as e:
        logger.error(f"Помилка виведення списку учнів: {e}")

async def main():
    logger.info("Запуск сервера...")
    await delete_webhook()  # Видалити активний вебхук
    logger.info("Запуск бота в режимі polling...")
    await connect_db()
    asyncio.create_task(dp.start_polling(bot))
    app.run(host="0.0.0.0", port=PORT)  # Запуск Flask

if __name__ == "__main__":
    asyncio.run(main())
