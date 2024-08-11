from database import get_user_channels

def get_channels_for_user(user_id: int):
    return get_user_channels(user_id)
