import os
import json
import logging
import psycopg2
from flask import Flask, request
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters, Dispatcher

# Завантажуємо змінні середовища
TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

# Налаштовуємо базу даних
Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Оголошення моделей
class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    students = relationship("Student", back_populates="group")

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    tg_id = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    group_id = Column(Integer, ForeignKey('groups.id'))
    group = relationship("Group", back_populates="students")

# Створюємо таблиці
Base.metadata.create_all(engine)

# Створюємо Flask застосунок
app = Flask(__name__)

def start(update: Update, context: CallbackContext):
    tg_id = str(update.message.from_user.id)
    user = session.query(Student).filter_by(tg_id=tg_id).first()
    
    if user:
        update.message.reply_text(f"Вітаю, {user.name}! Ви в групі {user.group.name}.", reply_markup=menu_keyboard())
    else:
        groups = session.query(Group).all()
        group_names = [[g.name] for g in groups]
        update.message.reply_text("Ви не зареєстровані. Виберіть вашу групу:", reply_markup=ReplyKeyboardMarkup(group_names, one_time_keyboard=True))

def register(update: Update, context: CallbackContext):
    tg_id = str(update.message.from_user.id)
    group_name = update.message.text
    group = session.query(Group).filter_by(name=group_name).first()
    
    if group:
        student = Student(tg_id=tg_id, name=update.message.from_user.full_name, group=group)
        session.add(student)
        session.commit()
        update.message.reply_text(f"Ви зареєстровані в групі {group.name}", reply_markup=menu_keyboard())
    else:
        update.message.reply_text("Такої групи не знайдено. Виберіть зі списку.")

def menu_keyboard():
    return ReplyKeyboardMarkup([
        ["📅 Розклад", "👨‍🏫 Контакти викладачів"],
        ["👥 Студенти групи"]
    ], resize_keyboard=True)

def schedule(update: Update, context: CallbackContext):
    update.message.reply_text("Тут буде розклад вашої групи.")

def contacts(update: Update, context: CallbackContext):
    update.message.reply_text("Тут будуть контакти викладачів.")

def students(update: Update, context: CallbackContext):
    tg_id = str(update.message.from_user.id)
    user = session.query(Student).filter_by(tg_id=tg_id).first()
    if user:
        group_students = session.query(Student).filter_by(group_id=user.group_id).all()
        student_names = "\n".join([s.name for s in group_students])
        update.message.reply_text(f"Ваші одногрупники:\n{student_names}")

def handle_message(update: Update, context: CallbackContext):
    if update.message.text in ["📅 Розклад", "👨‍🏫 Контакти викладачів", "👥 Студенти групи"]:
        commands = {"📅 Розклад": schedule, "👨‍🏫 Контакти викладачів": contacts, "👥 Студенти групи": students}
        commands[update.message.text](update, context)
    else:
        register(update, context)

# Налаштування вебхука
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(), bot)
    dispatcher.process_update(update)
    return "OK"

# Ініціалізація бота
bot = Updater(TOKEN, use_context=True).bot
dispatcher = Dispatcher(bot, None, workers=0)
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
