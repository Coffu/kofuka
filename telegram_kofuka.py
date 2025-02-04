import os
import json
import logging
import psycopg2
from flask import Flask, request
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from telegram import Update, ReplyKeyboardMarkup, Bot
from telegram.ext import CommandHandler, CallbackContext, MessageHandler, Filters, Dispatcher

app = Flask(__name__)

bot.set_webhook(url=f"https://kofuka-bk1t.onrender.com{TOKEN}")
# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

Base = declarative_base()
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Перевірка підключення до БД
try:
    with engine.connect() as conn:
        logger.info("Успішне підключення до бази даних!")
except Exception as e:
    logger.error(f"Помилка підключення до БД: {e}")

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

class Teacher(Base):
    __tablename__ = 'teachers'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    contact = Column(String)

Base.metadata.create_all(engine)

app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, workers=4)

def start(update: Update, context: CallbackContext):
    logger.info("Команда /start від користувача %s", update.message.from_user.id)
    tg_id = str(update.message.from_user.id)
    user = session.query(Student).filter_by(tg_id=tg_id).first()
    
    if user:
        update.message.reply_text(f"Вітаю, {user.name}! Ви в групі {user.group.name}.", reply_markup=menu_keyboard())
    else:
        groups = session.query(Group).all()
        group_names = [[g.name] for g in groups]
        update.message.reply_text("Ви не зареєстровані. Виберіть вашу групу:", reply_markup=ReplyKeyboardMarkup(group_names, one_time_keyboard=True))

def register(update: Update, context: CallbackContext):
    logger.info("Реєстрація користувача %s", update.message.from_user.id)
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
    logger.info("Запит розкладу від %s", update.message.from_user.id)
    tg_id = str(update.message.from_user.id)
    user = session.query(Student).filter_by(tg_id=tg_id).first()
    if user:
        update.message.reply_text(f"Тут буде розклад для групи {user.group.name}.")

def contacts(update: Update, context: CallbackContext):
    logger.info("Запит контактів викладачів від %s", update.message.from_user.id)
    teachers = session.query(Teacher).all()
    contacts_list = "\n".join([f"{t.name} ({t.subject}): {t.contact}" for t in teachers])
    update.message.reply_text(f"Контакти викладачів:\n{contacts_list}")

def students(update: Update, context: CallbackContext):
    logger.info("Запит студентів групи від %s", update.message.from_user.id)
    tg_id = str(update.message.from_user.id)
    user = session.query(Student).filter_by(tg_id=tg_id).first()
    if user:
        group_students = session.query(Student).filter_by(group_id=user.group_id).all()
        student_names = "\n".join([s.name for s in group_students])
        update.message.reply_text(f"Ваші одногрупники:\n{student_names}")

def handle_message(update: Update, context: CallbackContext):
    logger.info("Отримано повідомлення: %s", update.message.text)
    commands = {"📅 Розклад": schedule, "👨‍🏫 Контакти викладачів": contacts, "👥 Студенти групи": students}
    if update.message.text in commands:
        commands[update.message.text](update, context)
    else:
        register(update, context)

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    logger.info("Отримано оновлення з Telegram: %s", request.get_json())
    update = Update.de_json(request.get_json(), bot)
    dispatcher.process_update(update)
    return "OK"

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

if __name__ == "__main__":
    logger.info("Запуск сервера Flask")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
