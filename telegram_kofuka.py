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
    """ Перевірка користувача та реєстрація """
    user_id = message.from_user.id
    
    db = await connect_db()
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)

    if user:
        # Якщо користувач вже зареєстрований
        if user["group_id"]:
            # Якщо група вибрана, даємо доступ до основних кнопок
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
        # Якщо користувач не зареєстрований
        await message.answer("Введіть своє ім'я та прізвище для реєстрації:")

        # Очікуємо ім'я користувача
        @dp.message()
        async def register_user(message: types.Message):
            user_name = message.text
            db = await connect_db()

            # Додаємо нового користувача в базу
            await db.execute("INSERT INTO students (user_id, name) VALUES ($1, $2)", user_id, user_name)
            await message.answer("Ваше ім'я було успішно зареєстровано! Тепер виберіть групу.")

            # Отримуємо список груп
            groups = await db.fetch("SELECT id, name FROM groups")
            keyboard = ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text=group["name"])] for group in groups],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await message.answer("Оберіть свою групу:", reply_markup=keyboard)

@dp.message()
async def handle_group_selection(message: types.Message):
    """ Вибір групи """
    user_id = message.from_user.id
    db = await connect_db()

    # Перевірка, чи користувач вже зареєстрований і вибрав групу
    user = await db.fetchrow("SELECT * FROM students WHERE user_id=$1", user_id)
    if user and user["group_id"]:
        # Якщо група вже вибрана, даємо доступ до основних функцій
        await message.answer("Вітаю! Ось ваші доступні опції:", reply_markup=main_keyboard)
        return
    
    # Якщо група ще не вибрана, отримуємо список груп
    group_name = message.text
    group = await db.fetchrow("SELECT id FROM groups WHERE name=$1", group_name)
    
    if not group:
        await message.answer("Такої групи немає. Виберіть правильну групу.")
        return

    # Оновлюємо інформацію про групу користувача
    await db.execute("UPDATE students SET group_id=$1 WHERE user_id=$2", group["id"], user_id)
    
    # Після вибору групи надаємо доступ до основних функцій
    await message.answer("Ви успішно зареєстровані! Ось ваші доступні опції:", reply_markup=main_keyboard)

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

@dp.message(lambda message: message.text == "Контакти викладачів 👨‍🏫")
async def teacher_contacts(message: types.Message):
    """ Виведення контактів викладачів для групи користувача """
    user_id = message.from_user.id
    db = await connect_db()
    
    # Отримуємо group_id для користувача
    student = await db.fetchrow("SELECT group_id FROM students WHERE user_id=$1", user_id)

    if not student or not student["group_id"]:
        await message.answer("Вам потрібно вибрати групу перед переглядом контактів викладачів.")
        return

    # Отримуємо викладачів для цієї групи з таблиці teachers
    teachers = await db.fetch("SELECT name, subject, email FROM teachers WHERE group_id=$1", student["group_id"])
    
    if teachers:
        contacts_text = "\n".join([f"{teacher['name']} - {teacher['subject']} - {teacher['email']}" for teacher in teachers])
        await message.answer(f"Контакти викладачів для вашої групи:\n{contacts_text}")
    else:
        await message.answer("Контакти викладачів для вашої групи відсутні.")

@dp.message(lambda message: message.text == "Учні у групі 👥")
async def group_students(message: types.Message):
    """ Виведення учнів, які належать до тієї ж групи, що й користувач """
    user_id = message.from_user.id
    db = await connect_db()

    # Отримуємо group_id для користувача
    student = await db.fetchrow("SELECT group_id FROM students WHERE user_id=$1", user_id)

    if not student or not student["group_id"]:
        await message.answer("Вам потрібно вибрати групу перед переглядом учнів.")
        return

    # Отримуємо список учнів, які належать до цієї ж групи
    students_in_group = await db.fetch("SELECT name FROM students WHERE group_id=$1", student["group_id"])
    
    if students_in_group:
        students_list = "\n".join([student["name"] for student in students_in_group])
        await message.answer(f"Учні у вашій групі:\n{students_list}")
    else:
        await message.answer("Учні у вашій групі відсутні.")

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
