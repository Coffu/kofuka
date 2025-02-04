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

@dp.message(Command("start"))
async def start(message: types.Message):
    try:
        logger.info(f"Користувач {message.from_user.id} виконав команду /start")
        db = await connect_db()
        user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", message.from_user.id)
        if user:
            logger.info(f"Користувач {message.from_user.id} вже зареєстрований")
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            buttons = [KeyboardButton("Мій розклад"), KeyboardButton("Контакти викладачів"), KeyboardButton("Учні у групі")]
            keyboard.add(*buttons)
            await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=keyboard)
        else:
            logger.info(f"Користувач {message.from_user.id} не зареєстрований. Запит імені та прізвища.")
            await message.answer("Введіть своє ім'я та прізвище для реєстрації:")
    except Exception as e:
        logger.error(f"Помилка в обробці команди /start: {e}")

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
    # Запускаємо Flask у фоновому потоці
    flask_thread = Thread(target=run_flask)
    flask_thread.start()

    # Запускаємо asyncio-цикл
    asyncio.run(main())
