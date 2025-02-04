import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
import asyncpg
import asyncio
from flask import Flask, request
from threading import Thread

# Налаштування логування
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")  # Змінна середовища для токена
DATABASE_URL = os.getenv("DATABASE_URL")  # URL бази даних
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)

logger.info(f"Підключення до бази даних за адресою: {DATABASE_URL}")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db_pool = None  # Глобальне підключення до БД

# Підключення до бази даних з обробкою помилок
async def connect_db():
    global db_pool
    try:
        if db_pool is None:
            logger.info("Підключення до бази даних...")
            db_pool = await asyncpg.create_pool(DATABASE_URL)
        return db_pool
    except Exception as e:
        logger.error(f"Помилка підключення до бази даних: {e}")
        return None

# Головне меню
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Мій розклад")],
        [KeyboardButton(text="📚 Контакти викладачів")],
        [KeyboardButton(text="👥 Учні у групі")]
    ],
    resize_keyboard=True
)

start_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="🚀 Почати")]],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    logger.info(f"Користувач {message.from_user.id} розпочав роботу з ботом")
    await message.answer("👋 Вітаю! Я ваш навчальний бот. Натисніть '🚀 Почати', щоб продовжити.", reply_markup=start_menu)

@dp.message(lambda message: message.text == "🚀 Почати")
async def start_registration(message: types.Message):
    logger.info(f"Користувач {message.from_user.id} натиснув 'Почати'")
    db = await connect_db()
    if db is None:
        await message.answer("❌ Сталася помилка з підключенням до бази даних. Спробуйте пізніше.")
        logger.error(f"Не вдалося підключитися до бази даних для користувача {message.from_user.id}")
        return

    user_id = message.from_user.id
    student = await db.fetchrow("SELECT name FROM students WHERE user_id=$1", user_id)
    
    if student:
        logger.info(f"Користувач {user_id} вже зареєстрований: {student['name']}")
        await message.answer(f"🎉 Вітаю, {student['name']}! Обирайте дію з меню.", reply_markup=main_menu)
    else:
        logger.info(f"Користувач {user_id} не зареєстрований, запит на введення імені")
        await message.answer("📝 Введіть своє ім'я та прізвище для реєстрації:")

@dp.message()
async def handle_registration_or_menu(message: types.Message):
    logger.info(f"Користувач {message.from_user.id} ввів: {message.text}")
    db = await connect_db()
    if db is None:
        await message.answer("❌ Сталася помилка з підключенням до бази даних. Спробуйте пізніше.")
        logger.error(f"Не вдалося підключитися до бази даних для користувача {message.from_user.id}")
        return

    user_id = message.from_user.id
    student = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)
    
    if not student:
        logger.info(f"Користувач {user_id} не знайдений, реєстрація...")
        name_parts = message.text.split()
        if len(name_parts) < 2:
            await message.answer("⚠ Будь ласка, введіть ім'я та прізвище.")
            logger.warning(f"Користувач {user_id} ввів недостатньо даних (тільки одне ім'я або порожньо): {message.text}")
            return
        
        full_name = " ".join(name_parts)
        await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, full_name)
        
        groups = await db.fetch("SELECT name FROM groups")
        if not groups:
            await message.answer("❌ У системі немає доступних груп.")
            logger.warning("Немає доступних груп для вибору.")
            return
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=group["name"]) for group in groups]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer("📌 Оберіть свою групу:", reply_markup=keyboard)
    elif await db.fetchval("SELECT id FROM groups WHERE name=$1", message.text):
        group_id = await db.fetchval("SELECT id FROM groups WHERE name=$1", message.text)
        await db.execute("UPDATE students SET group_id=$1 WHERE user_id=$2", group_id, user_id)
        logger.info(f"Користувач {user_id} успішно зареєстрований у групі {message.text}")
        await message.answer("✅ Ви успішно зареєстровані в групі!", reply_markup=main_menu)
    elif message.text == "📅 Мій розклад":
        logger.info(f"Користувач {user_id} запитує розклад")
        schedule = await db.fetch("SELECT subject, time FROM schedule WHERE group_id=$1", student["group_id"])
        if schedule:
            schedule_text = "\n".join([f"⏰ {row['time']} - {row['subject']}" for row in schedule])
            await message.answer(f"📖 Ваш розклад:\n{schedule_text}")
        else:
            await message.answer("❌ Розклад не знайдено.")
            logger.warning(f"Користувач {user_id} не має розкладу.")
    elif message.text == "📚 Контакти викладачів":
        logger.info(f"Користувач {user_id} запитує контакти викладачів")
        contacts = await db.fetch("SELECT name, phone FROM teachers")
        contacts_text = "\n".join([f"👨‍🏫 {row['name']}: {row['phone']}" for row in contacts])
        await message.answer(f"📞 Контакти викладачів:\n{contacts_text}")
    elif message.text == "👥 Учні у групі":
        logger.info(f"Користувач {user_id} запитує список учнів у групі")
        students = await db.fetch("SELECT name FROM students WHERE group_id=$1", student["group_id"])
        students_text = "\n".join([f"👤 {row['name']}" for row in students])
        await message.answer(f"👨‍🎓 Учні вашої групи:\n{students_text}")
    else:
        await message.answer("❓ Невідома команда. Виберіть дію з меню.")
        logger.warning(f"Користувач {user_id} ввів невідому команду: {message.text}")

@app.route("/")
def index():
    logger.info("Бот працює!")
    return "Бот працює!"

if __name__ == "__main__":
    logger.info("Запуск бота...")
    app.run(host="0.0.0.0", port=PORT)
