import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from aiogram.fsm.storage.memory import MemoryStorage
import asyncpg
import asyncio
from flask import Flask
from threading import Thread

# 🔹 Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 🔹 Отримання змінних середовища
TOKEN = os.getenv("BOT_TOKEN")  
DATABASE_URL = os.getenv("DATABASE_URL")  
PORT = int(os.getenv("PORT", 5000))

# 🔹 Створення бота та диспетчера
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

app = Flask(__name__)

db_pool = None  # Пул підключень до БД

async def connect_db():
    """Функція підключення до бази даних."""
    global db_pool
    if db_pool is None:
        logger.info("Підключення до бази даних...")
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return db_pool

async def delete_webhook():
    """Видалення вебхука перед запуском бота."""
    try:
        await bot.delete_webhook()
        logger.info("Вебхук вимкнено.")
    except Exception as e:
        logger.error(f"Помилка вимкнення вебхука: {e}")

# 🔹 Клавіатури
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мій розклад 📅")],
        [KeyboardButton(text="Контакти викладачів 👨‍🏫")],
        [KeyboardButton(text="Учні у групі 👥")]
    ],
    resize_keyboard=True
)

start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Почати 🪄")]
    ],
    resize_keyboard=True
)

# 🔹 Обробники команд
@dp.message(Command("start"))
async def start_command(message: types.Message):
    """Вітання користувача та пропозиція почати"""
    logger.info(f"Користувач {message.from_user.id} виконав команду /start")
    await message.answer("Вітаю! Хочете почати? Натисніть кнопку 'Почати 🪄'.", reply_markup=start_keyboard)

@dp.message(lambda message: message.text == "Почати 🪄")
async def start_registration(message: types.Message):
    """Реєстрація користувача"""
    user_id = message.from_user.id
    db = await connect_db()
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)

    if user:
        await message.answer("Ви вже зареєстровані!", reply_markup=main_keyboard)
    else:
        await message.answer("Введіть своє ім'я та прізвище:")

@dp.message(lambda message: len(message.text.split()) >= 2)
async def handle_registration(message: types.Message):
    """Збереження імені користувача"""
    user_id = message.from_user.id
    db = await connect_db()

    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)
    if user:
        await message.answer("Ви вже зареєстровані!", reply_markup=main_keyboard)
        return

    full_name = message.text.strip()
    await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, full_name)

    groups = await db.fetch("SELECT name FROM groups")
    if not groups:
        await message.answer("Наразі немає доступних груп.")
        return

    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=group["name"])] for group in groups],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Оберіть свою групу:", reply_markup=keyboard)

@dp.message(lambda message: message.text in ["Мій розклад 📅", "Контакти викладачів 👨‍🏫", "Учні у групі 👥"])
async def handle_menu_selection(message: types.Message):
    """Обробка натискання кнопок меню"""
    user_id = message.from_user.id
    db = await connect_db()

    if message.text == "Мій розклад 📅":
        student = await db.fetchrow("SELECT group_id FROM students WHERE user_id=$1", user_id)
        if not student:
            await message.answer("Вас не знайдено у базі.")
            return

        schedule = await db.fetch("SELECT day, subject, time FROM schedule WHERE group_id=$1", student["group_id"])
        if schedule:
            schedule_text = "\n".join([f"{row['day']} - {row['subject']} о {row['time']}" for row in schedule])
            await message.answer(f"Ваш розклад:\n{schedule_text}")
        else:
            await message.answer("Розклад відсутній.")

    elif message.text == "Контакти викладачів 👨‍🏫":
        teachers = await db.fetch("SELECT name, phone FROM teachers")
        if teachers:
            contacts_text = "\n".join([f"{row['name']}: {row['phone']}" for row in teachers])
            await message.answer(f"Контакти викладачів:\n{contacts_text}")
        else:
            await message.answer("Контакти викладачів недоступні.")

    elif message.text == "Учні у групі 👥":
        student = await db.fetchrow("SELECT group_id FROM students WHERE user_id=$1", user_id)
        if not student:
            await message.answer("Вас не знайдено у базі.")
            return

        students = await db.fetch("SELECT name FROM students WHERE group_id=$1", student["group_id"])
        if students:
            students_text = "\n".join([row["name"] for row in students])
            await message.answer(f"Учні у вашій групі:\n{students_text}")
        else:
            await message.answer("Немає студентів у вашій групі.")

@app.route("/")
def keep_alive():
    return "Бот працює!"

def flask_thread():
    """Запуск Flask у фоновому потоці"""
    app.run(host="0.0.0.0", port=PORT)

async def main():
    """Головна функція"""
    await delete_webhook()
    Thread(target=flask_thread).start()
    logger.info("Бот запускається...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
