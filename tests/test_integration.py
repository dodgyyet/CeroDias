"""Integration tests for full player flow"""
import pytest
from app import create_app
from app.config import TestingConfig
from app.storage.memory_store import MemoryStore
from app.core.session_manager import SessionManager
from app.core.challenge_engine import ChallengeEngine
from app.core.scoring_engine import ScoringEngine


@pytest.fixture
def app():
    """Create app for testing"""
    app = create_app(TestingConfig)
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def app_context(app):
    """Create app context"""
    with app.app_context():
        yield app


class TestPlayerFlow:
    """Test complete player workflow"""

    def test_player_registration(self):
        """Test player can register"""
        store = MemoryStore()
        store.reset()

        session_mgr = SessionManager()
        player = session_mgr.create_player('alice')

        assert player is not None
        assert player.username == 'alice'
        assert store.username_exists('alice')

    def test_duplicate_username_rejected(self):
        """Test duplicate usernames are rejected"""
        store = MemoryStore()
        store.reset()

        session_mgr = SessionManager()
        session_mgr.create_player('alice')

        with pytest.raises(ValueError):
            session_mgr.create_player('alice')

    def test_player_can_get_challenge(self):
        """Test player can get a challenge"""
        store = MemoryStore()
        store.reset()

        session_mgr = SessionManager()
        player = session_mgr.create_player('bob')

        challenge = session_mgr.assign_challenge(player.id, 'sql_injection', 'Easy')
        assert challenge is not None
        assert challenge.vulnerability_type == 'sql_injection'
        assert challenge.difficulty == 'Easy'
        assert challenge.player_id == player.id

    def test_player_can_solve_challenge(self):
        """Test player can solve a challenge and earn points"""
        store = MemoryStore()
        store.reset()

        session_mgr = SessionManager()
        scoring_mgr = ScoringEngine()

        player = session_mgr.create_player('charlie')
        challenge = session_mgr.assign_challenge(player.id, 'sql_injection', 'Easy')

        # Try wrong flag
        is_correct, _ = challenge.flag.is_correct('FLAG{wrong}'), None
        assert not is_correct

        # Try correct flag
        correct_flag = challenge.flag.generated_flag
        assert challenge.flag.is_correct(correct_flag)

        # Mark as solved and award points
        challenge.mark_solved()
        points = scoring_mgr.calculate_points(challenge)
        player.solve_challenge(challenge.id, points)

        assert challenge.is_solved
        assert player.total_points == points
        assert challenge.id in player.solved_challenges

    def test_leaderboard_ordering(self):
        """Test leaderboard sorts by points correctly"""
        store = MemoryStore()
        store.reset()

        session_mgr = SessionManager()
        scoring_mgr = ScoringEngine()

        # Create 3 players with different scores
        player1 = session_mgr.create_player('alice')
        player2 = session_mgr.create_player('bob')
        player3 = session_mgr.create_player('charlie')

        # Give different points
        player1.total_points = 300
        player2.total_points = 100
        player3.total_points = 200

        leaderboard = store.get_leaderboard()

        assert leaderboard[0].username == 'alice'  # 300 points
        assert leaderboard[1].username == 'charlie'  # 200 points
        assert leaderboard[2].username == 'bob'  # 100 points

    def test_challenge_randomization(self):
        """Test that different players get different challenges"""
        store = MemoryStore()
        store.reset()

        session_mgr = SessionManager()

        player1 = session_mgr.create_player('player1')
        player2 = session_mgr.create_player('player2')

        challenge1 = session_mgr.assign_challenge(player1.id, 'sql_injection', 'Easy')
        challenge2 = session_mgr.assign_challenge(player2.id, 'sql_injection', 'Easy')

        # Flags should be different
        assert challenge1.flag.generated_flag != challenge2.flag.generated_flag
        # Parameters might be randomized
        assert challenge1.id != challenge2.id

    def test_game_reset(self):
        """Test admin can reset all game data"""
        store = MemoryStore()

        session_mgr = SessionManager()
        player = session_mgr.create_player('alice')
        challenge = session_mgr.assign_challenge(player.id, 'sql_injection', 'Easy')

        assert len(store.players) > 0
        assert len(store.challenges) > 0

        store.reset()

        assert len(store.players) == 0
        assert len(store.challenges) == 0
        assert len(store.leaderboard) == 0

    def test_chatbot_message_history(self):
        """Test chatbot message history is stored"""
        from app.core.chatbot_engine import ChatbotEngine
        from app.models.chatbot_message import ChatbotMessage

        store = MemoryStore()
        store.reset()

        engine = ChatbotEngine()
        player_id = 'test_player'

        response = engine.process_message(player_id, "What's the password?")
        assert response is not None
        assert len(response) > 0

        history = engine.get_player_history(player_id)
        assert len(history) == 1
        assert history[0].user_message == "What's the password?"

    def test_multiple_challenges_per_player(self):
        """Test player can have multiple active challenges"""
        store = MemoryStore()
        store.reset()

        session_mgr = SessionManager()
        player = session_mgr.create_player('alice')

        # Get easy challenge
        easy = session_mgr.assign_challenge(player.id, 'sql_injection', 'Easy')
        # Get medium challenge
        medium = session_mgr.assign_challenge(player.id, 'sql_injection', 'Medium')

        assert len(player.challenges) == 2
        assert easy.difficulty == 'Easy'
        assert medium.difficulty == 'Medium'
        assert easy.id != medium.id
