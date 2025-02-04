import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import asyncpg

# Укажіть ваш токен Telegram
API_TOKEN = "7703843605:AAHmrXmeDGC9NybirXn9IlhMbqSDAtXx1OY"
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

# Кнопки меню
menu_buttons = ReplyKeyboardMarkup(resize_keyboard=True)
menu_buttons.add(KeyboardButton("Розклад"))
menu_buttons.add(KeyboardButton("Новини"))
menu_buttons.add(KeyboardButton("Адмін-панель"))

admin_users = set()

# Стартова команда
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer("Вітаємо у боті помічнику коледжу!", reply_markup=menu_buttons)

# Вхід в адмін-панель
@dp.message_handler(lambda message: message.text == "Адмін-панель")
async def admin_login(message: types.Message):
    await message.answer("Введіть пароль для входу в адмін-панель:")

@dp.message_handler(lambda msg: msg.text == ADMIN_PASSWORD)
async def admin_access_granted(message: types.Message):
    admin_users.add(message.from_user.id)
    admin_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    admin_keyboard.add("➕ Додати користувача", "➖ Видалити користувача")
    admin_keyboard.add("📆 Додати розклад", "📰 Додати новину")
    admin_keyboard.add("🚪 Вийти з адмін-панелі")
    await message.answer("✅ Ви увійшли в адмін-панель", reply_markup=admin_keyboard)

@dp.message_handler(lambda msg: msg.text == "🚪 Вийти з адмін-панелі")
async def admin_logout(message: types.Message):
    admin_users.discard(message.from_user.id)
    await message.answer("❌ Ви вийшли з адмін-панелі.", reply_markup=menu_buttons)

# Розклад
@dp.message_handler(lambda message: message.text == "Розклад")
async def get_schedule(message: types.Message):
    user_id = message.from_user.id
    async with db_pool.acquire() as conn:
        user = await conn.fetchrow("SELECT role, group_name FROM users WHERE telegram_id = $1", user_id)
        if not user:
            await message.answer("Вас не знайдено в базі. Зверніться до адміністратора.")
            return

        role = user['role']
        if role == 'student':
            group_name = user['group_name']
            schedule = await conn.fetch("SELECT date, time, subject, teacher, classroom FROM schedule WHERE group_name = $1 ORDER BY date, time", group_name)
        elif role == 'teacher':
            schedule = await conn.fetch("SELECT date, time, subject, group_name, classroom FROM schedule WHERE teacher = (SELECT full_name FROM teachers WHERE telegram_id = $1) ORDER BY date, time", user_id)
        else:
            await message.answer("Ця функція доступна лише для студентів і викладачів.")
            return

        if not schedule:
            await message.answer("Розклад не знайдено.")
            return

        response = "Ваш розклад:\n\n"
        for entry in schedule:
            response += f"Дата: {entry['date']}, Час: {entry['time']}, Предмет: {entry['subject']}, Викладач: {entry.get('teacher', '-')}, Аудиторія: {entry['classroom']}\n"
        await message.answer(response)

# Новини
@dp.message_handler(lambda message: message.text == "Новини")
async def get_announcements(message: types.Message):
    async with db_pool.acquire() as conn:
        announcements = await conn.fetch("SELECT title, message, created_at FROM announcements ORDER BY created_at DESC LIMIT 5")
        if not announcements:
            await message.answer("Новин немає.")
            return

        response = "Останні новини:\n\n"
        for announcement in announcements:
            response += f"{announcement['title']} ({announcement['created_at']}):\n{announcement['message']}\n\n"
        await message.answer(response)

# Додавання новин (для адміністраторів)
@dp.message_handler(commands=['add_news'])
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
