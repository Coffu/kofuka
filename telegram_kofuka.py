import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import asyncpg

# Укажіть ваш токен Telegram
API_TOKEN = "7703843605:AAGq7-1tAvlBfNGKdtLHwTboO0HRYN3x4gk"

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

# Кнопки меню
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("Розклад"), KeyboardButton("Контакти вчителів"))
main_menu.add(KeyboardButton("Новини"))

def group_selection_keyboard(groups):
    keyboard = InlineKeyboardMarkup()
    for group in groups:
        keyboard.add(InlineKeyboardButton(group, callback_data=f"select_group:{group}"))
    return keyboard

# Стартова команда
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", message.from_user.id)
        if not user:
            await message.answer("Вітаємо! Введіть своє ім'я та прізвище для реєстрації:")
            return
    await message.answer("Вітаємо у боті помічнику коледжу!", reply_markup=main_menu)

# Реєстрація користувача
@dp.message_handler()
async def register_user(message: types.Message):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", message.from_user.id)
        if user:
            return

        await conn.execute("INSERT INTO users (telegram_id, name) VALUES ($1, $2)", message.from_user.id, message.text)

        groups = await conn.fetch("SELECT group_name FROM groups")
        group_names = [group['group_name'] for group in groups]
        await message.answer("Оберіть свою групу:", reply_markup=group_selection_keyboard(group_names))

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('select_group'))
async def select_group(callback_query: types.CallbackQuery):
    group_name = callback_query.data.split(':')[1]
    async with db_pool.acquire() as conn:
        await conn.execute("UPDATE users SET group_name = $1 WHERE telegram_id = $2", group_name, callback_query.from_user.id)
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Реєстрація завершена!", reply_markup=main_menu)

# Розклад
@dp.message_handler(lambda message: message.text == "Розклад")
async def show_schedule(message: types.Message):
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE telegram_id = $1", message.from_user.id)
        if not user or not user['group_name']:
            await message.answer("Ви не зареєстровані або не обрали групу.")
            return

        schedule = await conn.fetch("SELECT day, subject, time FROM schedule WHERE group_name = $1 ORDER BY day, time", user['group_name'])
        if not schedule:
            await message.answer("Розклад відсутній.")
            return

        response = "Розклад:
"
        for record in schedule:
            response += f"{record['day']} {record['time']}: {record['subject']}\n"

        await message.answer(response)

# Контакти вчителів
@dp.message_handler(lambda message: message.text == "Контакти вчителів")
async def show_teachers(message: types.Message):
    async with db_pool.acquire() as conn:
        teachers = await conn.fetch("SELECT name, contact FROM teachers")
        if not teachers:
            await message.answer("Контактна інформація відсутня.")
            return

        response = "Контакти вчителів:
"
        for teacher in teachers:
            response += f"{teacher['name']}: {teacher['contact']}\n"

        await message.answer(response)

# Новини
@dp.message_handler(lambda message: message.text == "Новини")
async def show_announcements(message: types.Message):
    async with db_pool.acquire() as conn:
        announcements = await conn.fetch("SELECT title, content FROM announcements ORDER BY id DESC LIMIT 5")
        if not announcements:
            await message.answer("Новин поки немає.")
            return

        response = "Останні новини:
"
        for news in announcements:
            response += f"{news['title']}: {news['content']}\n"

        await message.answer(response)

if __name__ == '__main__':
    async def on_startup(dp):
        global db_pool
        db_pool = await create_db_pool()
        logging.info("Бот запущено і база даних підключена.")

    async def on_shutdown(dp):
        await db_pool.close()
        logging.info("База даних відключена.")

    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)

