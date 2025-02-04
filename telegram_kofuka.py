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

TOKEN = os.getenv("BOT_TOKEN")  # Токен бота
DATABASE_URL = os.getenv("DATABASE_URL")  # URL бази даних
PORT = int(os.getenv("PORT", 5000))

app = Flask(__name__)

logger.info(f"DATABASE_URL: {DATABASE_URL}")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

db_pool = None  # Пул підключень до БД

async def connect_db():
    global db_pool
    if db_pool is None:
        logger.info("Підключення до бази даних...")
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return db_pool

async def delete_webhook():
    try:
        await bot.delete_webhook()
        logger.info("Вебхук вимкнено.")
    except Exception as e:
        logger.error(f"Помилка вимкнення вебхука: {e}")

# Головне меню після реєстрації
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мій розклад 📅")],
        [KeyboardButton(text="Контакти викладачів 👨‍🏫")],
        [KeyboardButton(text="Учні у групі 👥")]
    ],
    resize_keyboard=True
)

# Стартове меню
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Почати 🪄")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    """ Вітання користувача та пропозиція почати """
    logger.info(f"Користувач {message.from_user.id} виконав команду /start")
    await message.answer("Вітаю! Хочете почати? Натисніть кнопку 'Почати 🪄'.", reply_markup=start_keyboard)

@dp.message(lambda message: message.text == "Почати 🪄")
async def start_registration(message: types.Message):
    """ Перевірка користувача в БД та реєстрація, якщо потрібно """
    user_id = message.from_user.id
    db = await connect_db()
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)

    if user:
        logger.info(f"Користувач {user_id} вже зареєстрований")
        await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=main_keyboard)
    else:
        logger.info(f"Користувач {user_id} не зареєстрований. Запит імені.")
        await message.answer("Введіть своє ім'я та прізвище для реєстрації:")

@dp.message()
async def handle_registration(message: types.Message):
    """ Обробка введеного імені та вибір групи """
    user_id = message.from_user.id
    db = await connect_db()

    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)
    if user:
        await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=main_keyboard)
        return

    name_parts = message.text.split()
    if len(name_parts) < 2:
        await message.answer("Будь ласка, введіть своє ім'я та прізвище (наприклад: Іван Іванов).")
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

@dp.message()
async def handle_group_selection(message: types.Message):
    """ Обробка вибору групи """
    user_id = message.from_user.id
    db = await connect_db()

    group = await db.fetchrow("SELECT id FROM groups WHERE name=$1", message.text)
    if not group:
        await message.answer("Такої групи немає. Виберіть правильну групу.")
        return

    await db.execute("UPDATE students SET group_id=$1 WHERE user_id=$2", group["id"], user_id)
    await message.answer("Ви успішно зареєстровані! Ось ваші доступні опції:", reply_markup=main_keyboard)

@app.route("/")
def keep_alive():
    return "Бот працює!"

def flask_thread():
    """Запуск Flask в окремому потоці"""
    app.run(host="0.0.0.0", port=PORT)

async def main():
    """Основна функція"""
    await delete_webhook()
    Thread(target=flask_thread).start()
    logger.info("Бот запускається...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
