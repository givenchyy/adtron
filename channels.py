# channels.py

user_channels = {}

def add_user_channel(user_id, channel_name):
    if user_id not in user_channels:
        user_channels[user_id] = {'channels': []}
    if channel_name not in user_channels[user_id]['channels']:
        user_channels[user_id]['channels'].append(channel_name)
    print(f'Updated channels for user {user_id}: {user_channels[user_id]}')  # Debug print

def remove_user_channel(user_id, channel_name):
    if user_id in user_channels and channel_name in user_channels[user_id]['channels']:
        user_channels[user_id]['channels'].remove(channel_name)
        if not user_channels[user_id]['channels']:
            del user_channels[user_id]
    print(f'Updated channels for user {user_id}: {user_channels.get(user_id, {})}')  # Debug print

def get_user_channels(user_id):
    print(f'Getting channels for user {user_id}: {user_channels.get(user_id, {})}')  # Debug print
    return user_channels.get(user_id, {'channels': []})
