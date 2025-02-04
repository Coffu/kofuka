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
        logger.info("\U0001F4BB Підключення до бази даних...")
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return db_pool

async def delete_webhook():
    try:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url:
            logger.info(f"\U0001F5D1 Видалення активного вебхука: {webhook_info.url}")
            await bot.delete_webhook()
    except Exception as e:
        logger.error(f"\U000026A0 Помилка видалення вебхука: {e}")

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
    await message.answer("👋 Вітаю! Я ваш навчальний бот. Натисніть '🚀 Почати', щоб продовжити.", reply_markup=start_menu)

@dp.message(lambda message: message.text == "🚀 Почати")
async def start_registration(message: types.Message):
    db = await connect_db()
    user_id = message.from_user.id
    student = await db.fetchrow("SELECT name FROM students WHERE user_id=$1", user_id)
    
    if student:
        await message.answer(f"🎉 Вітаю, {student['name']}! Обирайте дію з меню.", reply_markup=main_menu)
    else:
        await message.answer("📝 Введіть своє ім'я та прізвище для реєстрації:")

@dp.message()
async def handle_registration_or_menu(message: types.Message):
    db = await connect_db()
    user_id = message.from_user.id
    student = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)
    
    if not student:
        name_parts = message.text.split()
        if len(name_parts) < 2:
            await message.answer("⚠ Будь ласка, введіть ім'я та прізвище.")
            return
        
        full_name = " ".join(name_parts)
        await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, full_name)
        
        groups = await db.fetch("SELECT name FROM groups")
        if not groups:
            await message.answer("❌ У системі немає доступних груп.")
            return
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text=group["name"])] for group in groups],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer("📌 Оберіть свою групу:", reply_markup=keyboard)
    elif message.text == "📅 Мій розклад":
        schedule = await db.fetch("SELECT subject, time FROM schedule WHERE group_id=$1", student["group_id"])
        if schedule:
            schedule_text = "\n".join([f"⏰ {row['time']} - {row['subject']}" for row in schedule])
            await message.answer(f"📖 Ваш розклад:\n{schedule_text}")
        else:
            await message.answer("❌ Розклад не знайдено.")
    elif message.text == "📚 Контакти викладачів":
        contacts = await db.fetch("SELECT name, phone FROM teachers")
        contacts_text = "\n".join([f"👨‍🏫 {row['name']}: {row['phone']}" for row in contacts])
        await message.answer(f"📞 Контакти викладачів:\n{contacts_text}")
    elif message.text == "👥 Учні у групі":
        students = await db.fetch("SELECT name FROM students WHERE group_id=$1", student["group_id"])
        students_text = "\n".join([f"👤 {row['name']}" for row in students])
        await message.answer(f"👨‍🎓 Учні вашої групи:\n{students_text}")
    else:
        await message.answer("❓ Невідома команда. Виберіть дію з меню.")

async def main():
    await delete_webhook()
    await connect_db()
    await dp.start_polling(bot)

def run_flask():
    app.run(host="0.0.0.0", port=PORT)

@app.route("/")
def index():
    return "🚀 Бот працює!"

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.run(main())
