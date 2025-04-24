import logging
import asyncio
from telegram.ext import Application, filters, CommandHandler, CallbackQueryHandler, MessageHandler
from config import TELEGRAM_BOT_TOKEN
from handlers import start, handle_text, button_click, help_command, handle_photo, login_command, logout_command
import nest_asyncio
from database import SessionLocal  # Імпортуєм SessionLocal з database/__init__.py

nest_asyncio.apply()

#logging.basicConfig(level=logging.DEBUG,
#                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',)

async def main():
    #налаштування логування
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Логування
    async def log_updates(update, context):
        print(f"Received update: {update}")
        return
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(MessageHandler(filters.ALL, log_updates), group=-1)
    # Ініціалізація Telegram бота


     # Ініціалізація bot_data при старті:
    application.bot_data['instagram_api'] = {}  # Словник для InstagramAPI
    application.bot_data['db_session'] = SessionLocal() #Додали сессію

    # Додавання обробників
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("login", login_command))
    application.add_handler(CommandHandler("logout", logout_command))
    application.add_handler(CallbackQueryHandler(button_click))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, handle_photo))

    print("🟢 Бот запущений!")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
