import sqlite3

# Инициализация базы данных
def initialize_db():
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()

    # Создаем таблицу пользователей и их каналы
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_channels (
            user_id INTEGER PRIMARY KEY,
            channels TEXT
        )
    ''')

    # Создаем таблицу запросов на взаимные посты
    c.execute('''
        CREATE TABLE IF NOT EXISTS post_requests (
            request_id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user_id INTEGER,
            to_channel TEXT,
            post_template TEXT,
            status TEXT
        )
    ''')

    # Создаем таблицу всех каналов
    c.execute('''
        CREATE TABLE IF NOT EXISTS all_channels (
            channel_name TEXT PRIMARY KEY,
            owner_id INTEGER
        )
    ''')

    conn.commit()
    conn.close()

# Функция для добавления нового канала в таблицу всех каналов
def add_all_channel(channel_name, owner_id):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()

    c.execute('INSERT OR REPLACE INTO all_channels (channel_name, owner_id) VALUES (?, ?)', (channel_name, owner_id))
    
    conn.commit()
    conn.close()

def get_channel_owner(channel_name):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()

    c.execute('SELECT owner_id FROM all_channels WHERE channel_name = ?', (channel_name,))
    result = c.fetchone()
    conn.close()

    if result:
        return result[0]
    return None

    conn = sqlite3.connect('channels.db')
    c = conn.cursor()

    c.execute('SELECT owner_id FROM all_channels WHERE channel_name = ?', (channel_name,))
    result = c.fetchone()
    conn.close()

    if result:
        return result[0]
    return None

# Функция для добавления канала пользователя
def add_user_channel(user_id, channel_name):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()

    # Проверка наличия пользователя
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

    if result:
        channels = result[0].split(',')
        return {'channels': channels}
    return {'channels': []}

# Функция для добавления запроса на взаимный пост
def add_post_request(from_user_id, to_channel, post_template, status):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()

    c.execute('INSERT INTO post_requests (from_user_id, to_channel, post_template, status) VALUES (?, ?, ?, ?)',
              (from_user_id, to_channel, post_template, status))
    
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

def update_post_request_status(from_user_id, to_channel, status):
    conn = sqlite3.connect('channels.db')
    c = conn.cursor()

    c.execute('UPDATE post_requests SET status = ? WHERE from_user_id = ? AND to_channel = ?', (status, from_user_id, to_channel))
    
    conn.commit()
    conn.close()