import sqlite3

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

    # Создаем таблицу статистики запросов
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_requests (
            user_id INTEGER PRIMARY KEY,
            request_count INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_db()
    print("Database initialized successfully.")
