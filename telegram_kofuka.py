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

# Отримання змінних середовища
TOKEN = os.getenv("BOT_TOKEN")  # Токен бота
DATABASE_URL = os.getenv("DATABASE_URL")  # URL бази даних
PORT = int(os.getenv("PORT", 5000))

# Створення об'єктів бота та диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

app = Flask(__name__)

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

# Стартове меню
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Почати 🪄")]
    ],
    resize_keyboard=True
)

@dp.message(Command("start"))
async def start_command(message: types.Message):
    """ Вітання користувача """
    logger.info(f"Користувач {message.from_user.id} виконав команду /start")
    await message.answer("Вітаю! Хочете почати? Натисніть кнопку 'Почати 🪄'.", reply_markup=start_keyboard)

@dp.message(lambda message: message.text == "Почати 🪄")
async def start_registration(message: types.Message):
    """ Початок реєстрації користувача """
    user_id = message.from_user.id
    db = await connect_db()

    # Перевіряємо, чи користувач вже зареєстрований
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)

    if user:
        # Якщо користувач уже є в базі
        await message.answer("Вітаємо! Ви вже зареєстровані.")
    else:
        # Якщо користувач не зареєстрований
        await message.answer("Введіть своє ім'я та прізвище для реєстрації:")
        # Зберігаємо ім'я користувача
        dp.register_message_handler(save_name_for_registration)

async def save_name_for_registration(message: types.Message):
    """ Збереження імені користувача в базі даних та повідомлення про успішну реєстрацію """
    user_id = message.from_user.id
    user_name = message.text
    db = await connect_db()

    # Додаємо користувача в базу даних
    await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, user_name)
    await message.answer(f"Ваше ім'я {user_name} було успішно зареєстровано! Тепер ви можете продовжити.")

@dp.message(lambda message: message.text == "Мій розклад 📅")
async def my_schedule(message: types.Message):
    """ Виведення розкладу для групи користувача """
    user_id = message.from_user.id
    db = await connect_db()
    student = await db.fetchrow("SELECT group_id FROM students WHERE user_id=$1", user_id)
    
    if not student or not student["group_id"]:
        await message.answer("Вам потрібно вибрати групу перед переглядом розкладу.")
        return

    schedule = await db.fetch("SELECT day, subject, time, classroom FROM schedule WHERE group_id=$1", student["group_id"])
    if schedule:
        schedule_text = "\n".join([f"{row['day']} - {row['subject']} о {row['time']} в {row['classroom']}" for row in schedule])
        await message.answer(f"Ваш розклад:\n{schedule_text}")
    else:
        await message.answer("Розклад відсутній.")

@app.route("/")
def keep_alive():
    return "Бот працює!"

def flask_thread():
    """ Запуск Flask у потоці """
    app.run(host="0.0.0.0", port=PORT)

async def main():
    await delete_webhook()
    Thread(target=flask_thread).start()
    logger.info("Бот запускається...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
