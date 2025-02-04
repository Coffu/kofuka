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
        [KeyboardButton(text="Почати 🪄")]
    ],
    resize_keyboard=True
)

student_panel_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мій розклад 📅")],
        [KeyboardButton(text="Контакти викладачів 👨‍🏫")],
        [KeyboardButton(text="Учні у групі 👥")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    try:
        logger.info(f"Користувач {message.from_user.id} виконав команду /start")
        await message.answer("Вітаю! Натисніть кнопку 'Почати 🪄' для продовження.", reply_markup=main_menu)
    except Exception as e:
        logger.error(f"Помилка в обробці команди /start: {e}")

@dp.message(lambda message: message.text == "Почати 🪄")
async def start_registration(message: types.Message):
    try:
        logger.info(f"Користувач {message.from_user.id} натиснув 'Почати 🪄'")
        db = await connect_db()
        user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", message.from_user.id)
        if user:
            logger.info(f"Користувач {message.from_user.id} вже зареєстрований")
            await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=student_panel_menu)
        else:
            logger.info(f"Користувач {message.from_user.id} не зареєстрований. Запит імені та прізвища.")
            await message.answer("Введіть своє ім'я та прізвище для реєстрації:")
    except Exception as e:
        logger.error(f"Помилка в обробці реєстрації: {e}")

@dp.message()
async def handle_message(message: types.Message):
    try:
        user_id = message.from_user.id
        db = await connect_db()

        logger.info(f"Користувач {user_id} ввів: {message.text}")

        student = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)
        if student:
            # Якщо користувач вже зареєстрований, показуємо панель учня
            await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=student_panel_menu)
            return

        name_parts = message.text.split()
        if len(name_parts) < 2:
            await message.answer("Будь ласка, введіть ім'я та прізвище.")
            return

        full_name = " ".join(name_parts)
        await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, full_name)

        logger.info(f"Користувача {user_id} зареєстровано як {full_name}")

        # Отримуємо список груп із бази даних
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
        logger.error(f"Помилка обробки повідомлення: {e}")

# Обробка кнопок панелі учня
@dp.message(lambda message: message.text == "Мій розклад 📅")
async def show_schedule(message: types.Message):
    try:
        db = await connect_db()
        user_id = message.from_user.id
        student = await db.fetchrow("SELECT group_id FROM students WHERE user_id=$1", user_id)
        if not student:
            await message.answer("Ви не зареєстровані!")
            return
        group_id = student["group_id"]
        schedule = await db.fetch("SELECT * FROM schedule WHERE group_id=$1", group_id)
        if not schedule:
            await message.answer("Розклад ще не додано.")
            return

        response = "\n".join([f"{item['subject']} - {item['time']}" for item in schedule])
        await message.answer(f"Ваш розклад:\n{response}")

    except Exception as e:
        logger.error(f"Помилка при показі розкладу: {e}")

@dp.message(lambda message: message.text == "Контакти викладачів 👨‍🏫")
async def show_teachers(message: types.Message):
    try:
        db = await connect_db()
        teachers = await db.fetch("SELECT name FROM teachers")
        if not teachers:
            await message.answer("У системі немає викладачів.")
            return

        response = "\n".join([f"👨‍🏫 {teacher['name']}" for teacher in teachers])
        await message.answer(f"Контакти викладачів:\n{response}")

    except Exception as e:
        logger.error(f"Помилка при показі викладачів: {e}")

@dp.message(lambda message: message.text == "Учні у групі 👥")
async def show_groupmates(message: types.Message):
    try:
        db = await connect_db()
        user_id = message.from_user.id
        student = await db.fetchrow("SELECT group_id FROM students WHERE user_id=$1", user_id)
        if not student:
            await message.answer("Ви не зареєстровані!")
            return
        group_id = student["group_id"]
        groupmates = await db.fetch("SELECT name FROM students WHERE group_id=$1", group_id)
        if not groupmates:
            await message.answer("В групі немає інших учнів.")
            return

        response = "\n".join([f"👥 {groupmate['name']}" for groupmate in groupmates])
        await message.answer(f"Учні вашої групи:\n{response}")

    except Exception as e:
        logger.error(f"Помилка при показі одногрупників: {e}")

async def main():
    logger.info("Запуск сервера...")
    await delete_webhook()  # Видалити активний вебхук
    logger.info("Запуск бота в режимі polling...")
    await connect_db()
    await dp.start_polling(bot)

def run_flask():
    logger.info("Запуск Flask-додатка у фоновому потоці")
    app.run(host="0.0.0.0", port=PORT)

@app.route("/")
def index():
    logger.info("Головна сторінка запиту доступна")
    return "Бот працює!"

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    asyncio.run(main())
