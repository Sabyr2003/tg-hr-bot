import os
import random
import aiosmtplib
import logging
import sqlite3
from dotenv import load_dotenv
from email.message import EmailMessage
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext, ConversationHandler
)

# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Настройка базы данных
DB_PATH = "hr_bot.db"

# Функция генерации ссылки Jitsi Meet
def create_meeting_link():
    meeting_id = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=10))
    return f"https://meet.jit.si/{meeting_id}"

# Обработчик кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message.text == "Создать конференцию":
        link = create_meeting_link()
        await update.message.reply_text(f"🔗 Ваша конференция: {link}")

# Главное меню
MAIN_MENU = [["Регистрация", "Подать заявку"], ["Список заявок", "Помощь"], ["Отправить резюме", "Создать конференцию"]]
KEYBOARD = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)


# Состояния диалога
POSITION, SALARY, REGION = range(3)


# Инициализация БД
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            first_name TEXT,
            last_name TEXT,
            username TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            position TEXT,
            salary INTEGER,
            region TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# Проверка регистрации
def is_user_registered(telegram_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user is not None

# Получение ID пользователя в БД
def get_user_id(telegram_id: int) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return user[0] if user else None

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Выберите действие:", reply_markup=KEYBOARD)

async def send_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Инструкция по загрузке резюме"""
    await update.message.reply_text("Отправь своё резюме в формате PDF или DOCX.")

# Регистрация
async def register(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if is_user_registered(user.id):
        await update.message.reply_text("Вы уже зарегистрированы!", reply_markup=KEYBOARD)
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (telegram_id, first_name, last_name, username) VALUES (?, ?, ?, ?)",
        (user.id, user.first_name, user.last_name, user.username)
    )
    conn.commit()
    conn.close()

    await update.message.reply_text("Регистрация завершена!", reply_markup=KEYBOARD)

# Подать заявку
async def submit_application(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_user_registered(update.effective_user.id):
        await update.message.reply_text("Сначала зарегистрируйтесь!", reply_markup=KEYBOARD)
        return ConversationHandler.END

    context.user_data["application"] = {}
    await update.message.reply_text("Введите вашу должность:")
    return POSITION

# Получение должности
async def process_position(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["application"]["position"] = update.message.text
    await update.message.reply_text("Введите желаемую зарплату:")
    return SALARY

# Получение зарплаты
async def process_salary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    salary_text = update.message.text
    if not salary_text.isdigit():
        await update.message.reply_text("Введите число!")
        return SALARY

    context.user_data["application"]["salary"] = int(salary_text)
    await update.message.reply_text("Введите ваш регион:")
    return REGION

# Получение региона и сохранение заявки
async def process_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["application"]["region"] = update.message.text
    user_id = get_user_id(update.effective_user.id)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO applications (user_id, position, salary, region) VALUES (?, ?, ?, ?)",
        (user_id, context.user_data["application"]["position"], context.user_data["application"]["salary"], context.user_data["application"]["region"])
    )
    conn.commit()
    conn.close()

    await update.message.reply_text("Ваша заявка сохранена!", reply_markup=KEYBOARD)
    return ConversationHandler.END

# Список заявок
async def list_applications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT position, salary, region FROM applications")
    applications = cursor.fetchall()
    conn.close()

    if not applications:
        await update.message.reply_text("Заявок нет.", reply_markup=KEYBOARD)
        return

    text = "📌 Список заявок:\n\n"
    for position, salary, region in applications:
        text += f"🔹 {position} | 💰 {salary} тенге | 📍 {region}\n"

    await update.message.reply_text("Очистка заявок: /clear_applications (Доступно только админу)")

    await update.message.reply_text(text, reply_markup=KEYBOARD)

# Очистка списка заявок (доступно только администратору)
async def clear_applications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    # Проверяем, является ли пользователь админом
    if user.username != "kinder_s_photo":
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM applications")
    conn.commit()
    conn.close()

    await update.message.reply_text("✅ Все заявки успешно удалены!")


# Обработчик кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text

    if text == "Регистрация":
        await register(update, context)
    elif text == "Подать заявку":
        await submit_application(update, context)
    elif text == "Список заявок":
        await list_applications(update, context)
    elif text == "Помощь":
        await update.message.reply_text("Доступные команды: /start, /register, /submit_application, /list_applications, /send_resume, /create_meeting_link", reply_markup=KEYBOARD)
    elif text == "Отправить резюме":
        await send_resume(update, context)
    elif text == "Создать конференцию":
        link = create_meeting_link()
        await update.message.reply_text(f"🔗 Ваша конференция: {link}")
    else:
        await update.message.reply_text("Я вас не понял. Выберите действие из меню.", reply_markup=KEYBOARD)

# 🔹 Данные для SMTP (Яндекс)
SMTP_SERVER = "smtp.yandex.ru"
SMTP_PORT = 465
SMTP_EMAIL = "sabyrzakirov1@yandex.ru"
SMTP_PASSWORD = "opwdvkbswqhwrxpb"

# Почта HR-менеджера
HR_EMAIL = "sabyrzakirov@gmail.com"

# Создаем папку для хранения резюме, если её нет
RESUMES_FOLDER = "resumes"
os.makedirs(RESUMES_FOLDER, exist_ok=True)

async def send_email(file_path: str, file_name: str):
    """Отправляет HR-менеджеру письмо с информацией о новом резюме"""
    msg = EmailMessage()
    msg["From"] = SMTP_EMAIL
    msg["To"] = HR_EMAIL
    msg["Subject"] = "📩 Новое резюме"

    msg.set_content(f"Здравствуйте,\n\nНовое резюме загружено:\n📎 {file_name}\n📂 Локальный путь: {file_path}")

    try:
        await aiosmtplib.send(msg, hostname=SMTP_SERVER, port=SMTP_PORT, use_tls=True, username=SMTP_EMAIL, password=SMTP_PASSWORD)
        print("📧 Резюме успешно отправлено HR-менеджеру!")
    except Exception as e:
        print(f"❌ Ошибка при отправке e-mail: {e}")

# Загружаем резюме
async def handle_document(update: Update, context: CallbackContext) -> None:
    """Обрабатывает загруженные документы и сохраняет их локально"""
    file = update.message.document
    file_name = file.file_name.lower()

    if not file_name.endswith(".pdf") and not file_name.endswith(".docx"):
        await update.message.reply_text("❌ Формат файла не поддерживается. Пришли PDF или DOCX.")
        return

    # Загружаем файл
    new_file = await file.get_file()
    file_path = os.path.join(RESUMES_FOLDER, file_name)
    await new_file.download_to_drive(file_path)

    await update.message.reply_text(f"✅ Резюме сохранено локально!\n📩 Отправляем HR...")

    # Отправляем e-mail HR
    await send_email(file_path, file_name)

    await update.message.reply_text(f"📧 HR-менеджер получил уведомление о резюме!")

# Запуск бота
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Подать заявку$"), submit_application)],
        states={
            POSITION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_position)],
            SALARY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_salary)],
            REGION: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_region)],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send_resume", send_resume))
    app.add_handler(CommandHandler("clear_applications", clear_applications))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))

    logging.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
