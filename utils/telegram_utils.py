from telegram import Bot

async def check_if_bot_can_post_messages(bot: Bot, chat_id: str) -> bool:
    try:
        chat_member = await bot.get_chat_member(chat_id, bot.id)
        return chat_member.status in ['administrator', 'creator'] and chat_member.can_post_messages
    except Exception as e:
        logging.error(f'Ошибка при проверке прав: {e}')
        return False
