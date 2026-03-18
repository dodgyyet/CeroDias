"""Player session management"""
from app.models.player import Player
from app.storage.memory_store import MemoryStore
from app.core.challenge_engine import ChallengeEngine


class SessionManager:
    """Manage player sessions and challenge assignment"""

    def __init__(self, seed=None):
        self.store = MemoryStore()
        self.challenge_engine = ChallengeEngine(seed=seed)

    def create_player(self, username):
        """
        Create a new player.

        Args:
            username: Desired username

        Returns:
            Player object, or None if username taken

        Raises:
            ValueError: If username invalid or already taken
        """
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters")

        if self.store.username_exists(username):
            raise ValueError("Username already taken")

        player = Player(username)
        self.store.add_player(player)
        return player

    def get_player(self, player_id):
        """Get player by ID"""
        return self.store.get_player(player_id)

    def get_player_by_username(self, username):
        """Get player by username"""
        return self.store.get_player_by_username(username)

    def assign_challenge(self, player_id, vuln_type, difficulty):
        """
        Assign a challenge to a player.

        Args:
            player_id: Player ID
            vuln_type: Vulnerability type
            difficulty: Difficulty level

        Returns:
            Challenge object
        """
        player = self.get_player(player_id)
        if not player:
            raise ValueError(f"Player not found: {player_id}")

        # Check if player already has this challenge
        for challenge in player.challenges.values():
            if (challenge.vulnerability_type == vuln_type and
                challenge.difficulty == difficulty and
                not challenge.is_solved):
                return challenge

        # Generate new challenge
        challenge = self.challenge_engine.generate_challenge(player_id, vuln_type, difficulty)
        player.add_challenge(challenge)
        self.store.add_challenge(challenge)

        return challenge

    def get_active_challenges(self, player_id):
        """Get unsolved challenges for a player"""
        player = self.get_player(player_id)
        if not player:
            return []
        return list(player.get_unsolved_challenges().values())

    def get_solved_challenges(self, player_id):
        """Get solved challenges for a player"""
        player = self.get_player(player_id)
        if not player:
            return []
        return list(player.get_solved_challenges().values())
