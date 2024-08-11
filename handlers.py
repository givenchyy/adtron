import logging
import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, ContextTypes
from database import (
    add_user_channel, remove_user_channel, get_user_channels,
    add_all_channel, get_all_channels, get_channel_owner,
    add_post_request, get_pending_requests, update_post_request_status
)
import httpx

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Глобальная переменная для хранения запросов
post_requests = {}


# Функция для получения количества подписчиков канала
async def get_channel_subscribers_count(chat_id: str, bot) -> int:
    url = f'https://api.telegram.org/bot{TOKEN}/getChatMembersCount'
    params = {'chat_id': chat_id}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        if response.status_code == 200:
            result = response.json()
            return result.get('result', 0)
        else:
            logging.error(f'Ошибка получения количества подписчиков: {response.status_code}')
            return 0

# Функция для старта бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Я бот для управления постами в каналах.')

async def is_user_member_of_channel(user_id: int, channel_username: str, bot) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f'Ошибка при проверке членства в канале @{channel_username}: {e}')
        return False

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
    if not context.args:
        await update.message.reply_text('Пожалуйста, укажите название канала после команды. Пример: /addchannel @channel_name')
        return
    
    channel_name = context.args[0].lstrip('@')
    chat_id = f'@{channel_name}'

    if await check_if_bot_can_post_messages(chat_id, context.bot):
        add_user_channel(user_id, channel_name)
        add_all_channel(channel_name, user_id)
        await update.message.reply_text(f'Канал @{channel_name} добавлен к вашему аккаунту.')
    else:
        await update.message.reply_text(f'Пожалуйста, убедитесь, что я имею право "Отправлять сообщения" в канале @{channel_name}.')

# Функция для удаления канала
async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not context.args:
        await update.message.reply_text('Пожалуйста, укажите название канала после команды. Пример: /removechannel @channel_name')
        return
    
    channel_name = context.args[0].lstrip('@')
    remove_user_channel(user_id, channel_name)
    await update.message.reply_text(f'Канал @{channel_name} удален из вашего аккаунта.')

# Функция для проверки прав на отправку сообщений
async def check_if_bot_can_post_messages(chat_id: str, bot) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id, bot.id)
        return chat_member.status in ['administrator', 'creator'] and chat_member.can_post_messages
    except Exception as e:
        logging.error(f'Ошибка при проверке прав: {e}')
        return False

# Функция для создания запроса на взаимный пост
async def create_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_channels = get_user_channels(user_id)
    
    if not user_channels['channels']:
        await update.message.reply_text(
            'У вас нет привязанных каналов. Используйте /addchannel @channel_name для добавления канала.'
        )
        return

    all_channels = get_all_channels()

    if all_channels:
        keyboard = [
            [InlineKeyboardButton(f'@{channel} ({await get_channel_subscribers_count(f"@{channel}", context.bot)} подписчиков)', callback_data=f'select_channel_{channel}')]
            for channel in all_channels
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Выберите канал для взаимного поста:', reply_markup=reply_markup)
    else:
        await update.message.reply_text('В базе данных нет доступных каналов для взаимного поста.')

# Функция для обработки нажатия кнопок выбора канала
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    if data.startswith('select_channel_'):
        channel_name = data[len('select_channel_'):]
        post_requests[user_id] = {'channel_name': channel_name, 'post_template': None, 'stage': 'request_sent'}
        await query.message.reply_text(f'Вы выбрали канал @{channel_name}. Пожалуйста, отправьте шаблон поста.')
        await query.message.delete()

    elif data.startswith(('confirm_', 'decline_')):
        action, channel_name, requester_id = data.split('_', 2)
        requester_id = int(requester_id)

        if action == 'confirm':
            await handle_confirm(requester_id, channel_name, context.bot)
        else:
            await handle_decline(requester_id, channel_name, context.bot)

        await query.message.delete()

def get_channel_name_by_user_id(user_id: int) -> str:
    user_channels = get_user_channels(user_id)
    return user_channels['channels'][0] if user_channels['channels'] else None

async def handle_confirm(requester_id: int, channel_name: str, bot):
    request = post_requests.get(requester_id)
    if request and request.get('stage') == 'request_sent':
        post_template = request.get('post_template', '')
        owner_id = get_channel_owner(channel_name)

        if owner_id:
            try:
                requesting_channel_name = get_channel_name_by_user_id(requester_id)
                logging.info(f'Отправка поста в канал @{channel_name} с шаблоном: {post_template}')
                await bot.send_message(chat_id=f'@{channel_name}', text=post_template)
                await bot.send_message(chat_id=requester_id, text=f'Ваш пост был успешно опубликован в канале @{channel_name}.')

                post_requests[owner_id] = {'channel_name': requesting_channel_name, 'post_template': None, 'stage': 'awaiting_reverse_post'}
                await bot.send_message(chat_id=owner_id, text=f'Теперь, пожалуйста, отправьте шаблон поста для канала @{requesting_channel_name}.')

                update_post_request_status(requester_id, channel_name, 'completed')
                post_requests[requester_id]['stage'] = 'completed'  # Обновляем этап

            except Exception as e:
                logging.error(f'Ошибка при отправке сообщения в канал {channel_name}: {e}')
                await bot.send_message(chat_id=requester_id, text='Не удалось отправить ваш пост в канал. Попробуйте позже.')
        else:
            await bot.send_message(chat_id=requester_id, text=f'Не удалось найти владельца канала @{channel_name}.')
    else:
        await bot.send_message(chat_id=requester_id, text='Не удалось найти шаблон поста для данного канала.')

# Обработка отклонения запроса
async def handle_decline(requester_id: int, channel_name: str, bot):
    await bot.send_message(chat_id=requester_id, text=f'Ваш запрос на взаимный пост от канала @{channel_name} был отклонен.')

# Функция для получения шаблона поста
async def receive_post_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    if user_id in post_requests:
        request = post_requests[user_id]
        if request.get('stage') == 'completed':
            return
        
        channel_name = request['channel_name']
        owner_id = get_channel_owner(channel_name)

        if owner_id:
            post_requests[user_id]['post_template'] = text

            if request['stage'] == 'request_sent':
                if user_id == owner_id:
                    await handle_reverse_post(user_id, channel_name, context.bot)
                else:
                    await send_post_request_to_owner(user_id, channel_name, text, context.bot)
            elif request['stage'] == 'awaiting_reverse_post':
                await handle_reverse_post(user_id, channel_name, context.bot)
        else:
            await update.message.reply_text(f'Не удалось найти владельца канала @{channel_name}.')
    else:
        await update.message.reply_text('Ваш запрос не найден или уже завершен.')

# Обработка обратного шаблона (владельца канала)
async def handle_reverse_post(user_id: int, channel_name: str, bot):
    original_channel = post_requests[user_id]['channel_name']
    post_template = post_requests[user_id]['post_template']
    
    logging.info(f'Отправка обратного поста в канал @{original_channel} с шаблоном: {post_template}')
    await bot.send_message(chat_id=f'@{original_channel}', text=post_template)
    await bot.send_message(chat_id=user_id, text=f'Ваш пост был успешно опубликован в канале @{original_channel}.')

    post_requests[user_id]['stage'] = 'completed'  # Обновляем этап
    await bot.send_message(chat_id=user_id, text='Ваш запрос был успешно выполнен. Спасибо за использование сервиса.')

    del post_requests[user_id]  # Удаляем завершенный запрос

# Отправка запроса владельцу канала
async def send_post_request_to_owner(requester_id: int, channel_name: str, post_template: str, bot):
    owner_id = get_channel_owner(channel_name)
    keyboard = [
        [InlineKeyboardButton("Принять", callback_data=f'confirm_{channel_name}_{requester_id}'),
         InlineKeyboardButton("Отклонить", callback_data=f'decline_{channel_name}_{requester_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await bot.send_message(chat_id=owner_id, text=f'Поступил запрос на взаимный пост от @{channel_name}. Шаблон:\n\n{post_template}', reply_markup=reply_markup)
