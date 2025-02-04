import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.fsm.storage.memory import MemoryStorage
from fastapi import FastAPI, Request

TOKEN = os.getenv("BOT_TOKEN")  # Змінна середовища для токена
WEBHOOK_PATH = f"/webhook/{TOKEN}"  # Унікальний шлях для вебхука
WEBHOOK_URL = "https://kofuka-bk1t.onrender.com" + WEBHOOK_PATH  # Замініть на URL Render

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
app = FastAPI()

logging.basicConfig(level=logging.INFO)

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    logging.info("Webhook встановлено!")

@app.post(WEBHOOK_PATH)
async def webhook_handler(update: dict):
    telegram_update = Update.model_validate(update)
    await dp.feed_update(bot, telegram_update)
    return {"status": "ok"}

@dp.message()
async def echo(message: types.Message):
    await message.answer("Привіт! Бот працює через вебхук!")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
