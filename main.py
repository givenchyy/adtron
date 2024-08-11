import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from handlers import check_subscription_callback, start, stats, add_channel, remove_channel, create_post, receive_post_template, button, top
from utils.logger import setup_logger
from initialize_db import initialize_db  # Импортируйте функцию инициализации

initialize_db()

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
setup_logger()

def main():
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        raise ValueError("Токен не найден в переменных окружения")

    application = Application.builder().token(TOKEN).build()

    # Команды
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('addchannel', add_channel))
    application.add_handler(CommandHandler('removechannel', remove_channel))
    application.add_handler(CommandHandler('createpost', create_post))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_post_template))
    application.add_handler(CommandHandler('top', top))
    application.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="check_subscription"))


    # Обработка нажатий на инлайн-кнопки
    application.add_handler(CallbackQueryHandler(button))

    application.run_polling()

if __name__ == '__main__':
    main()
