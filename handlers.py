import logging
import os
import sqlite3
import httpx
import html
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, ContextTypes, CallbackContext
from database import (
    add_user_channel, remove_user_channel, get_user_channels,
    add_all_channel, get_all_channels, get_channel_owner,
    add_post_request, get_pending_requests, update_post_request_status,
    get_top_users, update_request_count, update_user_request_count  # Убедитесь, что get_top_users импортирована
)


# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Глобальная переменная для хранения запросов
post_requests = {}

DATABASE = 'channels.db'


async def check_subscription(user_id: int, bot) -> bool:
    channel_username = '@adthrone'
    try:
        member = await bot.get_chat_member(chat_id=channel_username, user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        logging.error(f'Ошибка при проверке подписки на канал {channel_username}: {e}')
        return False
    
def require_subscription(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.message.from_user.id

        # Проверяем, подписан ли пользователь на обязательный канал
        if not await check_subscription(user_id, context.bot):
            keyboard = [
                [InlineKeyboardButton("Вступить в канал", url="https://t.me/adthrone")],
                [InlineKeyboardButton("Проверить подписку", callback_data="check_subscription")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                'Подпишитесь на канал @adthrone, чтобы использовать этого бота. После подписки, нажмите "Проверить подписку".',
                reply_markup=reply_markup
            )
            return  # Прерываем выполнение команды, если пользователь не подписан

        # Выполняем команду, если пользователь подписан
        return await func(update, context, *args, **kwargs)
    return wrapper

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

async def escape_html(text):
    return html.escape(text)

async def get_username(user_id, TOKEN):
    async with httpx.AsyncClient() as client:
        response = await client.post(f'https://api.telegram.org/bot{TOKEN}/getChat', params={'chat_id': user_id})
        data = response.json()
        if data['ok']:
            chat = data['result']
            return chat.get('username', None)
        else:
            logging.error(f"Ошибка при получении информации о пользователе: {data['description']}")
            return None

async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT user_id, request_count FROM user_requests ORDER BY request_count DESC')
    rows = c.fetchall()
    conn.close()

    if rows:
        top_text = "<b>Топ пользователей по количеству запросов:</b>\n\n"
        for idx, (user_id, request_count) in enumerate(rows, start=1):
            # Получаем список каналов для пользователя
            user_channels = get_user_channels(user_id)
            if user_channels['channels']:
                # Используем первый канал из списка
                channel_name = user_channels['channels'][0]
                subscribers_count = await get_channel_subscribers_count(f"@{channel_name}", context.bot)
                top_text += f"📊 <b>{idx}. @{channel_name} ({subscribers_count} подписчиков)</b> — <b>Запросов:</b> <code>{request_count}</code>\n"
            else:
                top_text += f"📊 <b>{idx}. User ID: {user_id}</b> — <b>Запросов:</b> <code>{request_count}</code>\n"

        # Добавление инструкции внизу
        current_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        escaped_time = await escape_html(current_time)  # Используйте await для вызова корутины
        top_text += f"\n<b>Обновлено на</b> {escaped_time}\n"
        top_text += "<b>Для получения статистики по вашему аккаунту используйте команду</b> /stats\n"

        logging.info(f"Отправляемое сообщение: {top_text}")

        try:
            await update.message.reply_text(top_text, parse_mode='HTML')
        except Exception as e:
            logging.error(f'Ошибка при отправке сообщения: {e}')
            await update.message.reply_text("Произошла ошибка при попытке отправить сообщение.")
    else:
        await update.message.reply_text("Топ пользователей пуст. Не было запросов.")

    
async def check_subscription_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = query.from_user.id

    # Проверяем, подписан ли пользователь на обязательный канал
    if await check_subscription(user_id, context.bot):
        await query.message.reply_text('Спасибо за подписку! Теперь вы можете использовать бота. /stats')
        # Здесь вы можете выполнить нужное действие, например, вызвать команду /start
        await start(update, context)
    else:
        await query.message.reply_text(
            'Вы еще не подписаны на канал @adthrone. Пожалуйста, подпишитесь и нажмите кнопку снова.'
        )
# Функция для старта бота
@require_subscription
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    
    # Сообщение приветствия
    response = 'Добро пожаловать! Вы успешно подписаны на канал.\n\n'

    # Добавление списка доступных команд
    response += '🛠️ <b>Доступные команды:</b>\n'
    response += '🔹 <code>/stats</code> — показать статистику пользователя\n'
    response += '🔹 <code>/addchannel @channel_name</code> — добавить канал\n'
    response += '🔹 <code>/removechannel @channel_name</code> — удалить канал\n'
    response += '🔹 <code>/createpost</code> — создать запрос на взаимный пост\n'
    response += '🔹 <code>/top</code> — топ пользователей\n'

    try:
        await update.message.reply_text(response, parse_mode='HTML')
    except Exception as e:
        logging.error(f'Ошибка при отправке сообщения: {e}')
        await update.message.reply_text("Произошла ошибка при попытке отправить сообщение.")

# Функция для обработки команды /stats
@require_subscription
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = await get_username(user_id, TOKEN)
    user_channels = get_user_channels(user_id)

    if not user_channels['channels']:
        await update.message.reply_text(
            'У вас нет привязанных каналов. Добавьте каналы с помощью команды /addchannel @channel_name.'
        )
        return

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute('SELECT request_count FROM user_requests WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()

    request_count = result[0] if result else 0

    response = f'🌟 <b>Личный кабинет пользователя</b> {"@" + username if username else ""} 🌟\n\n'
    response += '<b>Привязанные каналы:</b>\n'
    for index, channel in enumerate(user_channels['channels'], start=1):
        response += f'{index}. <a href="https://t.me/{channel}">@{channel}</a>\n'

    response += f'\n<b>Вы сделали {request_count} запросов на взаимные посты.</b>\n\n'
    response += '🛠️ <b>Доступные команды:</b>\n'
    response += '🔹 <code>/stats</code> — показать статистику пользователя\n'
    response += '🔹 <code>/addchannel @channel_name</code> — добавить канал\n'
    response += '🔹 <code>/removechannel @channel_name</code> — удалить канал\n'
    response += '🔹 <code>/createpost</code> — создать запрос на взаимный пост\n'
    response += '🔹 <code>/top</code> — топ пользователей\n'

    current_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    response += f'\n<b>Обновлено:</b> {current_time}'

    logging.info(f"Отправляемое сообщение: {response}")

    try:
        await update.message.reply_text(response, parse_mode='HTML')
    except Exception as e:
        logging.error(f'Ошибка при отправке сообщения: {e}')
        await update.message.reply_text("Произошла ошибка при попытке отправить сообщение.")


# Функция для добавления канала
@require_subscription
async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ваш код для обработки команды /addchannel
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
@require_subscription
async def remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ваш код для обработки команды /removechannel
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
@require_subscription
async def create_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Ваш код для обработки команды /createpost
    user_id = update.message.from_user.id
    user_channels = get_user_channels(user_id)

    if not user_channels['channels']:
        await update.message.reply_text(
            'У вас нет привязанных каналов. Используйте /addchannel @channel_name для добавления канала.'
        )
        return

    all_channels = get_all_channels()
    my_channel_name = get_channel_name_by_user_id(user_id)

    if all_channels:
        keyboard = [
            [InlineKeyboardButton(f'@{channel} ({await get_channel_subscribers_count(f"@{channel}", context.bot)} подписчиков)', callback_data=f'select_channel_{channel}')]
            for channel in all_channels
            if channel != my_channel_name
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
        owner_id = get_channel_owner(channel_name)

        if owner_id:
            try:
                requesting_channel_name = get_channel_name_by_user_id(requester_id)
                if requesting_channel_name != channel_name:  # Исключаем случаи, когда каналы совпадают
                    if 'photo' in request:  # Если есть фото
                        photo_file = request['photo']
                        caption = request.get('caption', '')  # Получаем подпись, если есть
                        logging.info(f'Отправляем фото в канал @{channel_name} с caption: {caption}')
                        await bot.send_photo(chat_id=f'@{channel_name}', photo=photo_file, caption=caption)
                    else:  # Если только текст
                        post_template = request.get('post_template', '')
                        logging.info(f'Отправляем текст в канал @{channel_name}: {post_template}')
                        await bot.send_message(chat_id=f'@{channel_name}', text=post_template)

                    # Отправка сообщения в канал, где был запрос
                    await bot.send_message(chat_id=requester_id, text=f'Ваш пост был успешно опубликован в канале @{channel_name}.')

                    post_requests[owner_id] = {'channel_name': requesting_channel_name, 'stage': 'awaiting_reverse_post'}
                    await bot.send_message(chat_id=owner_id, text=f'Теперь, пожалуйста, отправьте шаблон поста для канала @{requesting_channel_name}.')

                    update_post_request_status(requester_id, channel_name, 'completed')
                    post_requests[requester_id]['stage'] = 'completed'  # Обновляем этап

                else:
                    await bot.send_message(chat_id=requester_id, text='Вы не можете отправить пост в ваш собственный канал.')

            except Exception as e:
                logging.error(f'Ошибка при отправке сообщения в канал @{channel_name}: {e}')
                await bot.send_message(chat_id=requester_id, text='Не удалось отправить ваш пост в канал. Попробуйте позже.')
        else:
            await bot.send_message(chat_id=requester_id, text=f'Не удалось найти владельца канала @{channel_name}.')
    else:
        await bot.send_message(chat_id=requester_id, text='Не удалось найти шаблон поста для данного канала.')

# Обработка отклонения запроса
async def handle_decline(requester_id: int, channel_name: str, bot):
    await bot.send_message(chat_id=requester_id, text=f'Ваш запрос на взаимный пост от канала @{channel_name} был отклонен.')


async def handle_channel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    channel_name = query.data.replace('select_channel_', '')

    # Запрос шаблона поста от пользователя
    await query.message.reply_text(f'Вы выбрали канал @{channel_name}. Пожалуйста, отправьте шаблон поста.')

    # Устанавливаем состояние ожидания шаблона поста
    context.user_data['selected_channel'] = channel_name
    
# Функция для получения шаблона поста
async def receive_post_template(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id in post_requests:
        request = post_requests[user_id]
        if request.get('stage') == 'completed':
            return

        channel_name = request['channel_name']
        owner_id = get_channel_owner(channel_name)

        if owner_id:
            if update.message.photo:
                # Если получена фотография, сохраняем ее
                photo_file = update.message.photo[-1].file_id
                post_requests[user_id]['photo'] = photo_file
                post_requests[user_id]['caption'] = update.message.caption or ''
                await update.message.reply_text('Шаблон поста с фотографией успешно принят.')
            elif update.message.text:
                # Если получен текст, сохраняем его
                post_requests[user_id]['post_template'] = update.message.text
                await update.message.reply_text('Шаблон поста успешно принят.')
            
            # После получения шаблона отправляем запрос владельцу канала
            if request['stage'] == 'request_sent':
                if user_id == owner_id:
                    await handle_reverse_post(user_id, channel_name, context.bot)
                else:
                    await send_post_request_to_owner(user_id, channel_name, context.bot)
                update_user_request_count(user_id)
            elif request['stage'] == 'awaiting_reverse_post':
                await handle_reverse_post(user_id, channel_name, context.bot)
                update_user_request_count(user_id)
        else:
            await update.message.reply_text(f'Не удалось найти владельца канала @{channel_name}.')
    else:
        await update.message.reply_text('Ваш запрос не найден или уже завершен.')




# Обработка обратного шаблона (владельца канала)
async def handle_reverse_post(user_id: int, channel_name: str, bot):
    original_channel = post_requests[user_id]['channel_name']

    if 'photo' in post_requests[user_id]:  # Если есть фото
        await bot.send_photo(chat_id=f'@{original_channel}', photo=post_requests[user_id]['photo'], caption=post_requests[user_id].get('caption', ''))
    else:  # Если только текст
        await bot.send_message(chat_id=f'@{original_channel}', text=post_requests[user_id]['post_template'])

    await bot.send_message(chat_id=user_id, text=f'Ваш пост был успешно опубликован в канале @{original_channel}.')

    post_requests[user_id]['stage'] = 'completed'  # Обновляем этап
    await bot.send_message(chat_id=user_id, text='Ваш запрос был успешно выполнен. Спасибо за использование сервиса.')

    del post_requests[user_id]  # Удаляем завершенный запрос

# Отправка запроса владельцу канала
async def send_post_request_to_owner(requester_id: int, channel_name: str, bot):
    owner_id = get_channel_owner(channel_name)
    if not owner_id:
        logging.error(f'Не удалось найти владельца канала @{channel_name}.')
        return

    logging.info(f'Отправляем запрос владельцу канала @{channel_name}.')

    request = post_requests.get(requester_id, {})
    post_template = request.get('post_template', '')
    photo_file = request.get('photo')
    caption = request.get('caption', '') or post_template

    keyboard = [
        [InlineKeyboardButton("Принять", callback_data=f'confirm_{channel_name}_{requester_id}'),
         InlineKeyboardButton("Отклонить", callback_data=f'decline_{channel_name}_{requester_id}')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if photo_file:
            # Если есть фото, отправляем фото с подписью
            response = await bot.send_photo(
                chat_id=owner_id,
                photo=photo_file,
                caption=caption,
                reply_markup=reply_markup
            )
        else:
            # Если нет фото, отправляем только текст
            response = await bot.send_message(
                chat_id=owner_id,
                text=f'Поступил запрос на взаимный пост от @{channel_name}. Шаблон:\n\n{post_template}',
                reply_markup=reply_markup
            )

        logging.info(f'Запрос на пост отправлен владельцу канала @{channel_name}. Ответ: {response}')
    except Exception as e:
        logging.error(f'Ошибка при отправке запроса владельцу канала @{channel_name}: {e}')



