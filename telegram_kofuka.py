import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import asyncpg
import asyncio

# Завантажуємо змінні середовища
load_dotenv()

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Токен бота та URL бази даних
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Створення об'єктів бота та диспетчера
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Пул підключень до БД
db_pool = None

async def connect_db():
    global db_pool
    if db_pool is None:
        logger.info("Підключення до бази даних...")
        db_pool = await asyncpg.create_pool(DATABASE_URL)
    return db_pool

# Клавіатури
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Почати 🪄")]
    ],
    resize_keyboard=True
)

# Стартова команда
@dp.message(Command("start"))
async def start_command(message: types.Message):
    """ Вітання користувача і пропозиція почати реєстрацію """
    logger.info(f"Користувач {message.from_user.id} виконав команду /start")
    await message.answer(
        "Вітаю! Хочете почати? Натисніть кнопку 'Почати 🪄'.", reply_markup=start_keyboard)

# Обробка натискання на кнопку "Почати 🪄"
@dp.message(lambda message: message.text == "Почати 🪄")
async def start_registration(message: types.Message):
    """ Перевірка, чи є користувач в базі даних, і реєстрація, якщо його немає """
    user_id = message.from_user.id
    db = await connect_db()

    # Перевіряємо, чи користувач вже зареєстрований
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)

    if user:
        # Якщо користувач вже є, він переходить до основного меню
        await message.answer("Вітаю! Ось ваші доступні опції:")
        # Можна тут додати кнопки основного меню
    else:
        # Якщо користувач не знайдений, починається реєстрація
        await message.answer("Введіть своє ім'я для реєстрації:")
        
        # Створюємо стан для збору імені
        await dp.message_handler(lambda message: True)(save_name_for_registration)

# Окремий хендлер для збереження імені користувача
async def save_name_for_registration(message: types.Message):
    """ Збереження імені користувача в базі даних """
    user_id = message.from_user.id
    user_name = message.text
    db = await connect_db()

    # Додаємо користувача в базу даних
    await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, user_name)
    
    # Запитуємо групу
    await message.answer(f"Ваше ім'я {user_name} було успішно зареєстровано! Тепер виберіть свою групу.")
    
    # Потрібно додати логіку для вибору групи, але це можна зробити потім
    # Наприклад, можна створити список груп, як у попередніх версіях
    # Для цього використаємо клавіатуру з кнопками

    # Ваша логіка для вибору групи (вже пізніше додаємо)
    # groups = await db.fetch("SELECT id, name FROM groups")
    # keyboard = ReplyKeyboardMarkup(
    #     keyboard=[[KeyboardButton(text=group["name"])] for group in groups],
    #     resize_keyboard=True,
    #     one_time_keyboard=True
    # )
    # await message.answer("Оберіть свою групу:", reply_markup=keyboard)

# Запуск бота
async def main():
    logger.info("Бот запускається...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
