import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher.router import Router
from aiogram.dispatcher.filters import Command
from aiogram.types import Message
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import psycopg2
from datetime import datetime

# Логування
logging.basicConfig(level=logging.INFO)

# Токен бота
BOT_TOKEN = "7703843605:AAHmrXmeDGC9NybirXn9IlhMbqSDAtXx1OY"

# Параметри підключення до бази даних
DB_HOST = "dpg-cug3k0dsvqrc7383jdrg-a.ohio-postgres.render.com"
DB_NAME = "telegram_shop_48bs"
DB_USER = "telegram_shop_48bs_user"
DB_PASSWORD = "Lo8UMSqzNOUqRbGLbD0JAofPEdupoBug"

# Підключення до бази даних
try:
    conn = psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
except Exception as e:
    logging.error(f"Error connecting to the database: {e}")
    exit()

# Ініціалізація бота та диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Створення маршрутизатора
router = Router()
dp.include_router(router)

# Кнопки меню
builder = ReplyKeyboardBuilder()
builder.row(KeyboardButton(text="👗 Przeglądaj ubrania"))
builder.row(KeyboardButton(text="📦 Moje zamówienia"))

# Обробник команди /start
@router.message(Command("start"))
async def start_command(message: Message):
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
    except Exception as e:
        logging.error(f"Error handling /start: {e}")
        await message.reply("Wystąpił błąd podczas rejestracji użytkownika.")
        return

    await message.reply("Witaj w sklepie Kofuka! Wybierz opcję z menu:", reply_markup=builder.as_markup(resize_keyboard=True))

# Обробник кнопки "👗 Przeglądaj ubrania"
@router.message(lambda message: message.text == "👗 Przeglądaj ubrania")
async def show_products(message: Message):
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
        logging.error(f"Error fetching products: {e}")
        await message.reply("Wystąpił błąd podczas pobierania listy ubrań.")

# Обробник кнопки "📦 Moje zamówienia"
@router.message(lambda message: message.text == "📦 Moje zamówienia")
async def show_orders(message: Message):
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
        logging.error(f"Error fetching orders: {e}")
        await message.reply("Wystąpił błąd podczas pobierania zamówień.")

if __name__ == "__main__":
    from aiogram import Executor
    Executor.run_polling(dp, skip_updates=True)
