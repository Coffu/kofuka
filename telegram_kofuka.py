import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncpg

# Укажіть ваш токен Telegram
API_TOKEN = "7703843605:AAGq7-1tAvlBfNGKdtLHwTboO0HRYN3x4gk"
ADMIN_PASSWORD = "123456"

# Логування
logging.basicConfig(level=logging.INFO)

# Ініціалізація бота і диспетчера
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Підключення до бази даних
DB_CONFIG = {
    'user': 'pr_tg_user',
    'password': 'qKgOhgMjLsfAB1UtWtqHFSNcI7TM1PDT',
    'database': 'pr_tg',
    'host': 'dpg-cugmd1bv2p9s73cktkog-a',
    'port': 5432
}

async def create_db_pool():
    return await asyncpg.create_pool(**DB_CONFIG)

db_pool = None

admin_users = set()

# Стартова команда
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", message.from_user.id)
        if not user:
            await message.answer("Ви не зареєстровані. Введіть своє ім'я:")
            return
    
    menu_buttons = ReplyKeyboardMarkup(resize_keyboard=True)
    menu_buttons.add(KeyboardButton("Розклад"))
    menu_buttons.add(KeyboardButton("Новини"))
    await message.answer("Вітаємо у боті помічнику коледжу!", reply_markup=menu_buttons)

# Реєстрація користувача
@dp.message_handler()
async def register_user(message: types.Message):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", message.from_user.id)
        if user:
            return

        await conn.execute("INSERT INTO users (telegram_id, full_name) VALUES ($1, $2)", message.from_user.id, message.text)
        await message.answer("Тепер виберіть вашу групу.")

# Вхід в адмін-панель
@dp.message_handler(commands=['admin'])
async def admin_login(message: types.Message):
    await message.answer("Введіть пароль для доступу до адмін-панелі:")

    @dp.message_handler()
    async def check_password(msg: types.Message):
        if msg.text == ADMIN_PASSWORD:
            admin_users.add(msg.from_user.id)
            admin_buttons = ReplyKeyboardMarkup(resize_keyboard=True)
            admin_buttons.add(KeyboardButton("Додати предмет"))
            admin_buttons.add(KeyboardButton("Додати групу"))
            admin_buttons.add(KeyboardButton("Додати розклад"))
            admin_buttons.add(KeyboardButton("Додати новину"))
            await msg.answer("Вхід виконано. Ви в адмін-панелі.", reply_markup=admin_buttons)
        else:
            await msg.answer("Неправильний пароль.")

# Додавання новин (тільки для адмінів)
@dp.message_handler(lambda message: message.text == "Додати новину")
async def add_announcement(message: types.Message):
    if message.from_user.id not in admin_users:
        await message.answer("Ця команда доступна лише для адміністраторів.")
        return

    await message.answer("Введіть новину у форматі: Заголовок | Текст новини")

    @dp.message_handler()
    async def save_announcement(news_message: types.Message):
        try:
            title, message_text = map(str.strip, news_message.text.split('|', 1))
        except ValueError:
            await news_message.answer("Невірний формат. Використовуйте: Заголовок | Текст новини")
            return

        async with db_pool.acquire() as conn:
            await conn.execute("INSERT INTO announcements (title, message) VALUES ($1, $2)", title, message_text)
        await news_message.answer("Новину додано!")

if __name__ == '__main__':
    async def on_startup(dp):
        global db_pool
        db_pool = await create_db_pool()
        logging.info("Бот запущено і база даних підключена.")

    async def on_shutdown(dp):
        await db_pool.close()
        logging.info("База даних відключена.")

    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)
