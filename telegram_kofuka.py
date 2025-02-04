import os
from aiogram import Bot, Dispatcher, types
from aiogram.fsm import FSMContext
from aiogram.fsm.state import State
from aiogram.fsm.states import StatesGroup
from aiogram.utils import executor
from flask import Flask
from dotenv import load_dotenv
import asyncio

# Завантажуємо змінні середовища з .env файлу
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Ініціалізація ботів
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Стани для FSM (наприклад, для реєстрації)
class Registration(StatesGroup):
    waiting_for_name = State()  # Чекаємо ім'я

# Flask додаток
app = Flask(__name__)

@app.route("/upgrade", methods=["GET"])
def upgrade():
    """Метод для прив'язки порту через Flask."""
    return "Flask сервер працює, бот готовий!"

# Обробник стартової команди
@dp.message(commands=["start"])
async def start(message: types.Message):
    # Привітання і пропозиція почати реєстрацію
    await message.answer("Привіт! Якщо ти новий користувач, натисни 'Почати', щоб зареєструватися.", reply_markup=types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Почати")]
        ], resize_keyboard=True))

# Обробник кнопки "Почати"
@dp.message(lambda message: message.text.lower() == "почати")
async def process_start(message: types.Message):
    # Перевірка, чи є користувач у базі даних
    # Якщо користувач є в базі, то пропускаємо реєстрацію
    user_in_db = False  # Замість цього перевірте вашу базу
    if user_in_db:
        await message.answer("Ти вже зареєстрований!")
    else:
        await message.answer("Для початку реєстрації введіть ваше ім'я:")
        await Registration.waiting_for_name.set()

# Обробник введення імені
@dp.message(StateFilter(Registration.waiting_for_name))
async def save_name_for_registration(message: types.Message, state: FSMContext):
    # Збереження імені в базу даних (тут додайте ваш код)
    user_name = message.text
    await state.update_data(name=user_name)
    await message.answer(f"Ваше ім'я {user_name} збережено. Реєстрація завершена!")
    
    # Після реєстрації завершення
    await state.finish()

# Функція для запуску Flask сервера в окремому потоці
def run_flask():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))

# Асинхронна функція для запуску бота
async def start_bot():
    await executor.start_polling(dp, skip_updates=True)

# Запуск Flask та бота паралельно
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_bot())  # Запуск бота
    run_flask()  # Запуск Flask сервера
