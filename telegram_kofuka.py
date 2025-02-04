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

# Головне меню
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мій розклад 📅")],
        [KeyboardButton(text="Учні у групі 👥")],
        [KeyboardButton(text="Контакти викладачів 👨‍🏫")]
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
        logger.info(f"Користувач {user_id} вже зареєстрований.")
        # Якщо користувач вже зареєстрований, перевіряємо групу
        if user["group_id"]:
            await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=main_keyboard)
        else:
            # Якщо група не вибрана, пропонуємо вибрати групу
            groups = await db.fetch("SELECT id, name FROM groups")
            if not groups:
                await message.answer("У системі немає доступних груп.")
                return

            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=group["name"])] for group in groups],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer("Оберіть свою групу:", reply_markup=keyboard)
        return
    else:
        logger.info(f"Користувач {user_id} не зареєстрований. Починаємо реєстрацію.")
        # Якщо користувач не зареєстрований, запитуємо ім'я
        await message.answer("Введіть своє ім'я та прізвище для реєстрації:")

        # Додаємо нову фічу: створюємо стан реєстрації, щоб запитати групу після ім'я
        await dp.message_handler(lambda message: True)(save_name_for_registration)

# Окремий хендлер для збереження імені користувача в базі
async def save_name_for_registration(message: types.Message):
    """ Збереження імені користувача в базі даних та запит групи """
    user_id = message.from_user.id
    user_name = message.text
    db = await connect_db()

    # Додаємо користувача в базу даних
    logger.info(f"Додаємо користувача {user_id} з ім'ям {user_name} в базу даних.")
    await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, user_name)

    # Підтвердження, що ім'я було збережено
    await message.answer(f"Ваше ім'я {user_name} було успішно зареєстровано! Тепер виберіть свою групу.")
    
    # Запитуємо групу
    groups = await db.fetch("SELECT id, name FROM groups")
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
    """ Вибір групи після того, як користувач введе ім'я """
    user_id = message.from_user.id
    db = await connect_db()

    # Перевіряємо, чи користувач вже зареєстрований
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)

    if not user:
        logger.warning(f"Користувач {user_id} ще не зареєстрований!")
        await message.answer("Будь ласка, спочатку введіть своє ім'я для реєстрації.")
        return

    # Якщо користувач вибрав групу, оновлюємо інформацію в базі
    group_name = message.text
    group = await db.fetchrow("SELECT id FROM groups WHERE name=$1", group_name)

    if not group:
        await message.answer("Такої групи немає. Виберіть правильну групу.")
        return

    # Оновлюємо інформацію про групу користувача
    await db.execute("UPDATE students SET group_id=$1 WHERE user_id=$2", group["id"], user_id)
    
    # Після вибору групи надаємо доступ до основних функцій
    await message.answer("Ви успішно зареєстровані! Ось ваші доступні опції:", reply_markup=main_keyboard)

# Ось інші хендлери (наприклад, для розкладу, контактів викладачів та ін.)

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
