import sqlite3
import os
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
# Инициализация бота
bot = Bot(token=BOT_TOKEN)


# Функция для добавления нового канала в таблицу всех каналов
def add_all_channel(channel_name, owner_id):
    conn = sqlite3.connect("channels.db")
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO all_channels (channel_name, owner_id) VALUES (?, ?)', (channel_name, owner_id))
    conn.commit()
    conn.close()

# Функция для получения владельца канала
def get_channel_owner(channel_name):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()
    c.execute('SELECT owner_id FROM all_channels WHERE channel_name = ?', (channel_name,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

# Функция для добавления канала пользователя
def add_user_channel(user_id, channel_name):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()
    c.execute('SELECT channels FROM user_channels WHERE user_id = ?', (user_id,))
    result = c.fetchone()

    if result:
        channels = result[0].split(',')
        if channel_name not in channels:
            channels.append(channel_name)
            c.execute('UPDATE user_channels SET channels = ? WHERE user_id = ?', (','.join(channels), user_id))
    else:
        c.execute('INSERT INTO user_channels (user_id, channels) VALUES (?, ?)', (user_id, channel_name))
    
    conn.commit()
    conn.close()

# Функция для удаления канала пользователя
def remove_user_channel(user_id, channel_name):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()
    c.execute('SELECT channels FROM user_channels WHERE user_id = ?', (user_id,))
    result = c.fetchone()

    if result:
        channels = result[0].split(',')
        if channel_name in channels:
            channels.remove(channel_name)
            if channels:
                c.execute('UPDATE user_channels SET channels = ? WHERE user_id = ?', (','.join(channels), user_id))
            else:
                c.execute('DELETE FROM user_channels WHERE user_id = ?', (user_id,))
    
    conn.commit()
    conn.close()

# Функция для получения привязанных каналов пользователя
def get_user_channels(user_id):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()
    c.execute('SELECT channels FROM user_channels WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    conn.close()
    return {'channels': result[0].split(',') if result else []}

# Функция для добавления запроса на взаимный пост
def add_post_request(from_user_id, to_channel, post_template, status):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()
    
    # Вставляем новый запрос
    c.execute('INSERT INTO post_requests (from_user_id, to_channel, post_template, status) VALUES (?, ?, ?, ?)',
              (from_user_id, to_channel, post_template, status))
    
    print(f'Inserted post request: from_user_id={from_user_id}, to_channel={to_channel}, post_template={post_template}, status={status}')
    
    # Обновляем количество запросов для пользователя
    update_request_count(from_user_id, conn)

    conn.commit()
    conn.close()

# Функция для получения всех активных запросов пользователя
def get_pending_requests(user_id):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()
    c.execute('SELECT * FROM post_requests WHERE from_user_id = ? AND status = ?', (user_id, 'pending'))
    requests = c.fetchall()
    conn.close()
    return [{'request_id': req[0], 'from_user_id': req[1], 'to_channel': req[2], 'post_template': req[3], 'status': req[4]} for req in requests]

# Функция для получения всех привязанных каналов
def get_all_channels():
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()
    c.execute('SELECT channel_name FROM all_channels')
    result = c.fetchall()
    conn.close()
    return [row[0] for row in result]

# Функция для обновления статуса запроса
def update_post_request_status(from_user_id, to_channel, status):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()
    c.execute('UPDATE post_requests SET status = ? WHERE from_user_id = ? AND to_channel = ?', (status, from_user_id, to_channel))
    conn.commit()
    conn.close()

# Функция для получения количества подписчиков канала
def get_channel_subscribers(channel_name):
    try:
        chat = bot.get_chat(chat_id=channel_name)
        return chat.members_count
    except TelegramError as e:
        logger.error(f'Ошибка при получении количества подписчиков для канала {channel_name}: {e}')
        return 0

# Функция для обновления количества запросов пользователя
def update_request_count(user_id, conn):
    c = conn.cursor()
    
    # Проверяем, есть ли пользователь в таблице
    c.execute('SELECT request_count FROM user_requests WHERE user_id = ?', (user_id,))
    result = c.fetchone()

    if result:
        # Если есть, увеличиваем количество запросов
        request_count = result[0] + 1
        c.execute('UPDATE user_requests SET request_count = ? WHERE user_id = ?', (request_count, user_id))
    else:
        # Если нет, создаем новую запись
        c.execute('INSERT INTO user_requests (user_id, request_count) VALUES (?, ?)', (user_id, 1))
    
    conn.commit()

# Функция для получения топ пользователей по количеству запросов
def get_top_users(limit=10):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()
    c.execute('SELECT user_id, request_count FROM user_requests ORDER BY request_count DESC LIMIT ?', (limit,))
    top_users = c.fetchall()
    conn.close()
    return [{'user_id': user[0], 'request_count': user[1]} for user in top_users]

