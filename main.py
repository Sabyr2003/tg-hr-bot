import os
import random
import aiosmtplib
import logging
from dotenv import load_dotenv
from email.message import EmailMessage
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext, ConversationHandler
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

MAIN_MENU = [["Создать конференцию", "Отправить резюме"]]
KEYBOARD = ReplyKeyboardMarkup(MAIN_MENU, resize_keyboard=True)

def create_meeting_link():
    meeting_id = "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=10))
    return f"https://meet.jit.si/{meeting_id}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Выберите действие:", reply_markup=KEYBOARD)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = update.message.text
    if text == "Создать конференцию":
        link = create_meeting_link()
        await update.message.reply_text(f"🔗 Ваша конференция: {link}")
    elif text == "Отправить резюме":
        await update.message.reply_text("Отправь своё резюме в формате PDF или DOCX.")
    else:
        await update.message.reply_text("Я вас не понял. Выберите действие из меню.", reply_markup=KEYBOARD)

SMTP_SERVER = "smtp.yandex.ru"
SMTP_PORT = 465
SMTP_EMAIL = "sabyrzakirov1@yandex.ru"
SMTP_PASSWORD = "opwdvkbswqhwrxpb"
HR_EMAIL = "sabyrzakirov@gmail.com"
RESUMES_FOLDER = "resumes"
os.makedirs(RESUMES_FOLDER, exist_ok=True)

async def send_email(file_path: str, file_name: str):
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

async def handle_document(update: Update, context: CallbackContext) -> None:
    file = update.message.document
    file_name = file.file_name.lower()
    if not file_name.endswith(".pdf") and not file_name.endswith(".docx"):
        await update.message.reply_text("❌ Формат файла не поддерживается. Пришли PDF или DOCX.")
        return
    new_file = await file.get_file()
    file_path = os.path.join(RESUMES_FOLDER, file_name)
    await new_file.download_to_drive(file_path)
    await update.message.reply_text(f"✅ Резюме сохранено локально!\n📩 Отправляем HR...")
    await send_email(file_path, file_name)
    await update.message.reply_text(f"📧 HR-менеджер получил уведомление о резюме!")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, button_handler))
    logging.info("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
