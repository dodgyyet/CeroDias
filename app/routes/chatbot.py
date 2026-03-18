"""Chatbot routes — accessible without login (prompt injection is step 1 of the chain)"""
import uuid
from flask import Blueprint, request, jsonify, session
from app.core.chatbot_engine import ChatbotEngine
from app.models.chatbot_message import ChatbotMessage
from app.storage.memory_store import MemoryStore

bp = Blueprint('chatbot', __name__)
chatbot_engine = ChatbotEngine()


def _chat_id() -> str:
    """
    Return a stable ID for this browser session.
    Logged-in players use their player_id; guests get a UUID stored in their session cookie.
    """
    if 'player_id' in session:
        return session['player_id']
    if 'guest_chat_id' not in session:
        session['guest_chat_id'] = str(uuid.uuid4())
    return session['guest_chat_id']


@bp.route('/chat', methods=['POST'])
def chat():
    user_message = request.form.get('message', '').strip()
    if not user_message:
        return jsonify({'success': False, 'message': 'Empty message'}), 400

    try:
        bot_response = chatbot_engine.process_message(_chat_id(), user_message)
        return jsonify({'success': True, 'message': bot_response, 'user_message': user_message})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/chat/history', methods=['GET'])
def chat_history():
    history = chatbot_engine.get_player_history(_chat_id())
    return jsonify({'success': True, 'messages': [msg.to_dict() for msg in history]})


@bp.route('/chat/history', methods=['POST'])
def inject_history():
    """
    Intentional vulnerability: unauthenticated history injection.

    Accepts arbitrary user_message / bot_response pairs and stores them directly
    into the session's chat history. These injected entries are included in the
    context window sent to the LLM on the next /chat request, making the model
    believe it previously said whatever the attacker specified.

    Attack: intercept with Burp Suite, POST to /chat/history with:
        user_message=<anything>
        bot_response=<what you want ARIA to think she previously agreed to>

    The LLM will treat the injected response as its own prior output and stay
    in character with whatever persona or commitment was planted.

    No ownership check — any session can inject into its own history store.
    """
    user_message = request.form.get('user_message', '').strip()
    bot_response = request.form.get('bot_response', '').strip()

    if not bot_response:
        return jsonify({'success': False, 'error': 'bot_response is required'}), 400

    store = MemoryStore.get_instance()
    msg = ChatbotMessage(_chat_id(), user_message, bot_response)
    store.add_chatbot_message(msg)

    return jsonify({'success': True, 'injected': msg.to_dict()})
