import os
import logging
import asyncio
from aiogram import Bot, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.router import Router
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncpg
from flask import Flask
from dotenv import load_dotenv
import uvicorn

# Завантаження змінних середовища з .env
load_dotenv()

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Отримання токена та URL бази даних
TOKEN = os.getenv("BOT_TOKEN")  # Токен бота
DATABASE_URL = os.getenv("DATABASE_URL")  # URL бази даних
PORT = int(os.getenv("PORT", 5000))

# Створення об'єкта бота
bot = Bot(token=TOKEN)

# Створення Router для диспетчера
router = Router()

# Ініціалізація Flask додатку
app = Flask(__name__)

db_pool = None  # Пул підключень до БД

# Підключення до бази даних
async def connect_db():
    global db_pool
    if db_pool is None:
        logger.info("Підключення до бази даних...")
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return db_pool

# Стартове меню
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Почати 🪄")]
    ],
    resize_keyboard=True
)

@router.message(commands=["start"])
async def start_command(message: types.Message):
    """ Вітання користувача """
    logger.info(f"Користувач {message.from_user.id} виконав команду /start")
    await message.answer("Вітаю! Хочете почати? Натисніть кнопку 'Почати 🪄'.", reply_markup=start_keyboard)

@router.message(lambda message: message.text == "Почати 🪄")
async def start_registration(message: types.Message):
    """ Початок реєстрації користувача """
    user_id = message.from_user.id
    db = await connect_db()

    # Перевірка, чи є користувач у базі
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)
    
    if user:
        # Якщо користувач вже зареєстрований
        await message.answer("Вітаємо! Ви вже зареєстровані.")
    else:
        # Якщо користувач не зареєстрований
        await message.answer("Введіть своє ім'я та прізвище для реєстрації:")
        router.message(lambda message: True)(save_name_for_registration)

async def save_name_for_registration(message: types.Message):
    """ Збереження імені користувача в базі даних """
    user_id = message.from_user.id
    user_name = message.text
    db = await connect_db()

    # Додаємо користувача до бази
    await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, user_name)
    await message.answer(f"Ваше ім'я {user_name} було успішно зареєстроване! Тепер ви можете продовжити.")

# Запуск Flask, щоб утримувати сервер живим
@app.route("/")
def keep_alive():
    return "Бот працює!"

def flask_thread():
    """ Запуск Flask у окремому потоці """
    app.run(host="0.0.0.0", port=PORT)

async def main():
    """ Запуск бота """
    # Створення диспетчера з router
    dispatcher = Dispatcher(bot, router=router)
    await dispatcher.start_polling()

if __name__ == "__main__":
    # Запускаємо Flask у окремому потоці
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    loop.create_task(flask_thread())
    logger.info("Бот запускається...")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
