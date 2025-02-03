import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import psycopg2
from datetime import datetime

# Логування
logging.basicConfig(level=logging.INFO)

# Отримання конфігурації зі змінних середовища
BOT_TOKEN = os.getenv("7703843605:AAHmrXmeDGC9NybirXn9IlhMbqSDAtXx1OY
")
DATABASE_URL = os.getenv("postgresql://telegram_shop_48bs_user:Lo8UMSqzNOUqRbGLbD0JAofPEdupoBug@dpg-cug3k0dsvqrc7383jdrg-a.ohio-postgres.render.com/telegram_shop_48bs")

# Перевірка змінних середовища
if not BOT_TOKEN:
    logging.error("Змінна середовища BOT_TOKEN не налаштована!")
    exit()

if not DATABASE_URL:
    logging.error("Змінна середовища DATABASE_URL не налаштована!")
    exit()

# Підключення до бази даних
try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    logging.info("Підключення до бази даних встановлено.")
except Exception as e:
    logging.error(f"Помилка підключення до бази даних: {e}")
    exit()

# Ініціалізація бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Кнопки меню
main_menu = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu.add(KeyboardButton("👗 Przeglądaj ubrania"))
main_menu.add(KeyboardButton("📦 Moje zamówienia"))

# Обробник команди /start
@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or "Anonim"
    full_name = message.from_user.full_name

    try:
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            cursor.execute(
                "INSERT INTO users (id, username, full_name, created_at) VALUES (%s, %s, %s, %s)",
                (user_id, username, full_name, datetime.now())
            )
            conn.commit()
            logging.info(f"Новий користувач зареєстрований: {username} ({user_id})")
    except Exception as e:
        logging.error(f"Помилка при реєстрації користувача: {e}")
        await message.reply("Виникла помилка під час реєстрації.")
        return

    await message.reply("Witaj w sklepie Kofuka! Wybierz opcję z menu:", reply_markup=main_menu)

# Обробник кнопки "👗 Przeglądaj ubrania"
@dp.message_handler(lambda message: message.text == "👗 Przeglądaj ubrania")
async def show_products(message: types.Message):
    try:
        cursor.execute("SELECT id, name, price FROM products")
        products = cursor.fetchall()

        if not products:
            await message.reply("Brak dostępnych ubrań.")
        else:
            response = "🛍️ Dostępne ubrania:\n"
            for product in products:
                response += f"{product[0]}. {product[1]} - {product[2]:.2f} PLN\n"
            await message.reply(response)
    except Exception as e:
        logging.error(f"Помилка отримання списку продуктів: {e}")
        await message.reply("Виникла помилка під час отримання списку продуктів.")

# Обробник кнопки "📦 Moje zamówienia"
@dp.message_handler(lambda message: message.text == "📦 Moje zamówienia")
async def show_orders(message: types.Message):
    user_id = message.from_user.id
    try:
        cursor.execute(
            "SELECT orders.id, products.name, orders.total_price, orders.created_at FROM orders "
            "JOIN products ON orders.product_id = products.id WHERE orders.user_id = %s",
            (user_id,)
        )
        orders = cursor.fetchall()

        if not orders:
            await message.reply("Nie masz jeszcze żadnych zamówień.")
        else:
            response = "📦 Twoje zamówienia:\n"
            for order in orders:
                response += (
                    f"Zamówienie #{order[0]}: {order[1]}\n"
                    f"Cena: {order[2]:.2f} PLN\n"
                    f"Data: {order[3].strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                )
            await message.reply(response)
    except Exception as e:
        logging.error(f"Помилка отримання замовлень: {e}")
        await message.reply("Виникла помилка під час отримання замовлень.")

# Запуск бота
async def main():
    dp.startup.register(lambda: logging.info("Бот успішно запущений!"))
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
