from database import add_user_channel, remove_user_channel, get_user_channels, get_channel_owner, get_all_channels

def add_channel_to_user(user_id: int, channel_name: str):
    add_user_channel(user_id, channel_name)

def remove_channel_from_user(user_id: int, channel_name: str):
    remove_user_channel(user_id, channel_name)

def get_owner_of_channel(channel_name: str):
    return get_channel_owner(channel_name)
