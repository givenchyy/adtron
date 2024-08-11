import logging
import os
import sqlite3
from dotenv import load_dotenv
from database import get_all_users
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, CallbackContext, filters
from utils.telegram_utils import is_admin  # Импортируйте функцию проверки админа

# Создание объекта bot с использованием токена
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
bot = Bot(token=TOKEN)

async def get_username(user_id: int, bot: Bot) -> str:
    try:
        chat = await bot.get_chat(user_id)
        return chat.username if chat.username else 'Неизвестно'
    except Exception as e:
        logging.error(f'Ошибка при получении информации о пользователе {user_id}: {e}')
        return 'Неизвестно'

async def handle_admin_panel_callback(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    query = update.callback_query

    if query.data.startswith("block_"):
        try:
            blocked_user_id = int(query.data.split("_")[1])
            blocked_username = await get_username(blocked_user_id, context.bot)
            
            conn = sqlite3.connect('channels.db')
            c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO blocked_users (user_id, username) VALUES (?, ?)', 
                      (blocked_user_id, blocked_username))
            conn.commit()
            conn.close()

            await query.message.reply_text(f"Пользователь {blocked_username} (ID: {blocked_user_id}) заблокирован.")

            try:
                await context.bot.send_message(
                    chat_id=blocked_user_id,
                    text="Вы заблокированы и не имеете права выполнять команды."
                )
            except Exception as e:
                logging.error(f"Ошибка при отправке сообщения пользователю {blocked_user_id}: {e}")

            await query.message.delete()

        except ValueError:
            await query.message.reply_text("Ошибка: некорректный ID пользователя.")
        except Exception as e:
            await query.message.reply_text(f"Произошла ошибка при блокировке пользователя: {e}")

    elif query.data.startswith("unblock_"):
        try:
            unblocked_user_id = int(query.data.split("_")[1])
            conn = sqlite3.connect('channels.db')
            c = conn.cursor()
            c.execute('DELETE FROM blocked_users WHERE user_id = ?', (unblocked_user_id,))
            conn.commit()
            conn.close()

            unblocked_username = await get_username(unblocked_user_id, context.bot)

            await query.message.reply_text(f"Пользователь {unblocked_username} (ID: {unblocked_user_id}) разблокирован.")

            try:
                await context.bot.send_message(
                    chat_id=unblocked_user_id,
                    text="Вы больше не заблокированы и можете использовать команды бота."
                )
            except Exception as e:
                logging.error(f"Ошибка при отправке сообщения пользователю {unblocked_user_id}: {e}")

            await query.message.delete()

        except ValueError:
            await query.message.reply_text("Ошибка: некорректный ID пользователя.")
        except Exception as e:
            await query.message.reply_text(f"Произошла ошибка при разблокировке пользователя: {e}")

    elif query.data == "admin_panel" and is_admin(user_id):
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔒 Заблокировать пользователя", callback_data="show_user_list")],
            [InlineKeyboardButton("🔓 Разблокировать пользователя", callback_data="show_blocked_user_list")],
            [InlineKeyboardButton("🌟 Выдать VIP-статус", callback_data="give_vip")],
            [InlineKeyboardButton("📢 Отправить сообщение", callback_data="send_announcement")]
        ])
        await query.message.reply_text("Админ-панель:", reply_markup=markup)

    elif query.data == "show_user_list" and is_admin(user_id):
        await send_user_list(update, context)

    elif query.data == "show_blocked_user_list" and is_admin(user_id):
        await send_blocked_user_list(update, context)

    elif query.data == "give_vip" and is_admin(user_id):
        await query.message.reply_text("Введите ID пользователя для выдачи VIP-статуса:")
        # Регистрация обработчика для этого сообщения

    elif query.data == "send_announcement" and is_admin(user_id):
        await query.message.reply_text("Введите сообщение для рассылки:")
        # Регистрация обработчика для этого сообщения

    else:
        await query.message.reply_text("У вас нет доступа к этой функции.")

async def send_blocked_user_list(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.message.reply_text("У вас нет доступа к этой функции.")
        return

    conn = sqlite3.connect('channels.db')
    c = conn.cursor()
    c.execute('SELECT user_id, username FROM blocked_users')
    blocked_users = c.fetchall()
    conn.close()

    if not blocked_users:
        await update.callback_query.message.reply_text("Нет заблокированных пользователей.")
        return

    keyboard = [[InlineKeyboardButton(f"Разблокировать {user[1] or user[0]}", callback_data=f"unblock_{user[0]}")] for user in blocked_users]
    markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.reply_text("Выберите пользователя для разблокировки:", reply_markup=markup)

async def handle_admin_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if is_admin(user_id):
        text = update.message.text
        if text.isdigit():
            blocked_user_id = int(text)
            blocked_username = await get_username(blocked_user_id, context.bot)
            conn = sqlite3.connect('channels.db')
            c = conn.cursor()
            c.execute('INSERT OR IGNORE INTO blocked_users (user_id, username) VALUES (?, ?)', (blocked_user_id, blocked_username))
            conn.commit()
            conn.close()
            await update.message.reply_text(f"Пользователь {blocked_username} (ID: {blocked_user_id}) заблокирован.")
        else:
            await update.message.reply_text("Некорректный ввод. Введите числовой ID пользователя.")
    else:
        await update.message.reply_text("У вас нет доступа к этой функции.")

async def send_user_list(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.callback_query.message.reply_text("У вас нет доступа к этой функции.")
        return

    users = get_all_users()  # Получите всех пользователей
    keyboard = []
    for user_id in users:
        username = await get_username(user_id, context.bot)
        keyboard.append([InlineKeyboardButton(f"@{username}", callback_data=f"block_{user_id}")])
    
    markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.message.reply_text("Выберите пользователя для блокировки:", reply_markup=markup)

def register_admin_handlers(application):
    application.add_handler(CallbackQueryHandler(handle_admin_panel_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_message))
    application.add_handler(CommandHandler('showusers', send_user_list))
    application.add_handler(CommandHandler('showblockedusers', send_blocked_user_list))
