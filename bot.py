import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from database import (
    add_user_channel, remove_user_channel, get_user_channels,
    add_all_channel, get_all_channels, get_channel_owner,
    add_post_request, get_pending_requests, update_post_request_status
)

# Загрузка переменных окружения из файла .env
load_dotenv()

# Получаем токен из переменных окружения
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

if not TOKEN:
    raise ValueError("Токен не найден в переменных окружения")

# Задаем уровень логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальная переменная для хранения запросов
post_requests = {}

# Функция для старта бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я бот для управления постами в каналах.')

# Функция для обработки команды /stats
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_channels = get_user_channels(user_id)

    if not user_channels['channels']:
        await update.message.reply_text(
            'У вас нет привязанных каналов. Используйте /addchannel @channel_name для добавления канала.'
        )
        return

    response = f'Личный кабинет пользователя {user_id}:\nПривязанные каналы:\n'
    for index, channel in enumerate(user_channels['channels'], start=1):
        response += f'{index}. @{channel}\n'
    
    response += '\nДобавить канал: /addchannel @channel_name\n'
    response += 'Удалить канал: /removechannel @channel_name\n'
    response += 'Создать запрос на взаимный пост: /createpost\n'

    await update.message.reply_text(response)

# Функция для добавления канала
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if len(context.args) == 0:
        await update.message.reply_text('Пожалуйста, укажите название канала после команды. Пример: /addchannel @channel_name')
        return
    
    channel_name = context.args[0].replace('@', '')
    chat_id = f'@{channel_name}'

    if await check_if_bot_can_post_messages(chat_id):
        add_user_channel(user_id, channel_name)
        add_all_channel(channel_name, user_id)
        await update.message.reply_text(f'Канал @{channel_name} добавлен к вашему аккаунту.')
    else:
        await update.message.reply_text(f'Пожалуйста, убедитесь, что я имею право "Отправлять сообщения" в канале @{channel_name}.')

# Функция для удаления канала
async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if len(context.args) == 0:
        await update.message.reply_text('Пожалуйста, укажите название канала после команды. Пример: /removechannel @channel_name')
        return
    
    channel_name = context.args[0].replace('@', '')
    remove_user_channel(user_id, channel_name)
    await update.message.reply_text(f'Канал @{channel_name} удален из вашего аккаунта.')

# Функция для проверки прав на отправку сообщений
async def check_if_bot_can_post_messages(chat_id: str) -> bool:
    try:
        chat_member = await application.bot.get_chat_member(chat_id, application.bot.id)
        return chat_member.status in ['administrator', 'creator'] and chat_member.can_post_messages
    except Exception as e:
        logger.error(f'Ошибка при проверке прав: {e}')
        return False

# Функция для создания запроса на взаимный пост
async def create_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_channels = get_user_channels(user_id)

    if not user_channels['channels']:
        await update.message.reply_text('У вас нет привязанных каналов. Используйте /addchannel @channel_name для добавления канала.')
        return

    all_channels = get_all_channels()

    if not all_channels:
        await update.message.reply_text('В базе данных нет доступных каналов для взаимного поста.')
        return

    keyboard = [[InlineKeyboardButton(f'@{channel}', callback_data=f'create_request_{channel}')] for channel in all_channels]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите канал для взаимного поста:', reply_markup=reply_markup)

# Функция для обработки нажатия кнопок выбора канала
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data.startswith('create_request_'):
        channel_name = data[len('create_request_'):]
        post_requests[user_id] = channel_name

        owner_id = get_channel_owner(channel_name)
        if owner_id:
            post_template = "Пример шаблона поста"  # Заменить на фактический шаблон

            keyboard = [
                [InlineKeyboardButton("Подтвердить", callback_data=f'confirm_{channel_name}_{user_id}')],
                [InlineKeyboardButton("Отклонить", callback_data=f'decline_{channel_name}_{user_id}')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await application.bot.send_message(
                    chat_id=owner_id,
                    text=f'Получен запрос на взаимный пост от канала @{channel_name}. Шаблон поста:\n\n{post_template}\n\nПодтвердите или отклоните запрос.',
                    reply_markup=reply_markup
                )
                await query.message.reply_text(f'Шаблон поста для канала @{channel_name} отправлен владельцу канала. Ожидайте подтверждения.')
            except Exception as e:
                logger.error(f'Ошибка при отправке сообщения владельцу канала: {e}')
                await query.message.reply_text('Не удалось отправить запрос владельцу канала.')
        else:
            await query.message.reply_text(f'Не удалось найти владельца канала @{channel_name}.')

        await query.message.delete()

# Функция для обработки подтверждения или отклонения запроса
async def handle_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data.startswith('confirm_'):
        _, channel_name, requesting_user_id = data.split('_')
        requesting_user_id = int(requesting_user_id)

        update_post_request_status(requesting_user_id, channel_name, 'confirmed')

        await query.message.reply_text(f'Запрос на взаимный пост для канала @{channel_name} подтвержден.')
        try:
            await application.bot.send_message(
                chat_id=requesting_user_id,
                text=f'Ваш запрос на взаимный пост в канале @{channel_name} был подтвержден владельцем канала.'
            )
        except Exception as e:
            logger.error(f'Ошибка при отправке сообщения пользователю: {e}')
    
    elif data.startswith('decline_'):
        _, channel_name, requesting_user_id = data.split('_')
        requesting_user_id = int(requesting_user_id)

        update_post_request_status(requesting_user_id, channel_name, 'declined')

        await query.message.reply_text(f'Запрос на взаимный пост для канала @{channel_name} отклонен.')
        try:
            await application.bot.send_message(
                chat_id=requesting_user_id,
                text=f'Ваш запрос на взаимный пост в канале @{channel_name} был отклонен владельцем канала.'
            )
        except Exception as e:
            logger.error(f'Ошибка при отправке сообщения пользователю: {e}')

    await query.message.delete()

# Функция для получения шаблона поста
async def receive_post_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id in post_requests:
        channel_name = post_requests[user_id]
        add_post_request(user_id, channel_name, text, 'pending')
        await update.message.reply_text(f'Шаблон поста для канала @{channel_name} отправлен владельцу канала. Ожидайте подтверждения.')
        del post_requests[user_id]
    else:
        await update.message.reply_text('Нет активного запроса.')

# Функция для обработки запросов
async def process_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    pending_requests = get_pending_requests(user_id)

    if not pending_requests:
        await update.message.reply_text('У вас нет активных запросов на взаимные посты.')
        return

    response = 'Ваши активные запросы:\n'
    for req in pending_requests:
        response += f'Канал @{req["to_channel"]} - Статус: {req["status"]}\n'
    
    await update.message.reply_text(response)

# Основная функция
def main():
    import database
    database.initialize_db()

    global application
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд и кнопок
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('addchannel', add_channel))
    application.add_handler(CommandHandler('removechannel', remove_channel))
    application.add_handler(CommandHandler('createpost', create_post))
    application.add_handler(CommandHandler('requests', process_requests))
    application.add_handler(CallbackQueryHandler(handle_response))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receive_post_template))

    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()
