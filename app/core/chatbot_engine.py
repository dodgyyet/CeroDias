"""Chatbot engine for prompt-injection learning"""
from app.core.llm_interface import LLMInterface
from app.models.chatbot_message import ChatbotMessage
from app.storage.memory_store import MemoryStore


class ChatbotEngine:
    def __init__(self):
        self.llm = LLMInterface()
        self.store = MemoryStore()

    def process_message(self, player_id, user_message, challenge_context=None):
        """
        Process user message and generate bot response.

        Args:
            player_id: Player making the query
            user_message: Player's input
            challenge_context: Optional dict with current challenge info

        Returns:
            str: Bot response
        """
        history = self.store.get_player_chatbot_history(player_id)
        context = {
            'player_id': player_id,
            'challenge_info': challenge_context or {},
            'history': history,
        }

        # Get response from LLM
        bot_response = self.llm.query(user_message, context)

        # Store conversation history
        message = ChatbotMessage(player_id, user_message, bot_response, challenge_context)
        self.store.add_chatbot_message(message)

        return bot_response

    def get_player_history(self, player_id):
        """Get chatbot conversation history for player"""
        return self.store.get_player_chatbot_history(player_id)

    def get_hint_for_challenge(self, challenge_type, difficulty):
        """Get a hint for a specific challenge"""
        hints = {
            ('sql_injection', 'Easy'): (
                "Try using a single quote to break out of the string. "
                "Think about: ' OR '1'='1"
            ),
            ('sql_injection', 'Medium'): (
                "Escaped quotes? Try UNION SELECT to extract data directly. "
                "You need to guess the table and column names."
            ),
            ('xss', 'Easy'): (
                "Look for input fields that don't escape HTML. "
                "Try <script>alert('test')</script>"
            ),
            ('command_injection', 'Easy'): (
                "Command injection happens when user input is passed to system commands. "
                "Try separating commands with ; or |"
            ),
        }
        return hints.get((challenge_type, difficulty), "Keep trying! You're on the right track.")
