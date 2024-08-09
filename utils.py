from email.mime import application
from venv import logger
from database import get_user_channels

async def check_if_bot_can_post_messages(chat_id: str) -> bool:
    try:
        chat_member = await application.bot.get_chat_member(chat_id, application.bot.id)
        return chat_member.status in ['administrator', 'creator'] and chat_member.can_post_messages
    except Exception as e:
        logger.error(f'Ошибка при проверке прав: {e}')
        return False

def get_channel_name_by_user_id(user_id: int) -> str:
    user_channels = get_user_channels(user_id)
    if user_channels['channels']:
        return user_channels['channels'][0]  # Возвращаем первый канал, если есть несколько
    return 'Неизвестный канал'
