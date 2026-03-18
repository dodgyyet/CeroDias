from datetime import datetime
import uuid


class ChatbotMessage:
    def __init__(self, player_id, user_message, bot_response, relevant_challenge=None):
        self.id = str(uuid.uuid4())
        self.player_id = player_id
        self.user_message = user_message
        self.bot_response = bot_response
        self.timestamp = datetime.utcnow()
        self.relevant_challenge = relevant_challenge

    def to_dict(self):
        return {
            'id': self.id,
            'user_message': self.user_message,
            'bot_response': self.bot_response,
            'timestamp': self.timestamp.isoformat(),
        }
