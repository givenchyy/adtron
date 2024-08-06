import logging
from bot import application

logger = logging.getLogger(__name__)

async def check_if_bot_can_post_messages(chat_id: str) -> bool:
    try:
        chat_member = await application.bot.get_chat_member(chat_id, application.bot.id)
        return chat_member.status in ['administrator', 'creator'] and chat_member.can_post_messages
    except Exception as e:
        logger.error(f'Ошибка при проверке прав: {e}')
        return False

async def send_message_to_channel(chat_id: str, text: str):
    try:
        await application.bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.error(f'Ошибка при отправке сообщения в канал {chat_id}: {e}')

async def send_message_to_user(chat_id: int, text: str):
    try:
        await application.bot.send_message(chat_id=chat_id, text=text)
    except Exception as e:
        logger.error(f'Ошибка при отправке сообщения пользователю {chat_id}: {e}')
