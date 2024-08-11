from database import add_post_request, update_post_request_status

def create_post_request(user_id: int, channel_name: str, post_template: str):
    add_post_request(user_id, channel_name, post_template)

def mark_request_as_completed(user_id: int, channel_name: str):
    update_post_request_status(user_id, channel_name, 'completed')
