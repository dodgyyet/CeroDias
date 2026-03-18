from datetime import datetime
import uuid


class Player:
    def __init__(self, username):
        self.id = str(uuid.uuid4())
        self.username = username
        self.created_at = datetime.utcnow()
        self.challenges = {}  # challenge_id -> Challenge
        self.solved_challenges = set()  # challenge_id set
        self.total_points = 0
        self.chatbot_messages = []  # List of ChatbotMessage

    def add_challenge(self, challenge):
        """Add a challenge to this player"""
        self.challenges[challenge.id] = challenge

    def solve_challenge(self, challenge_id, points):
        """Mark challenge as solved and award points"""
        self.solved_challenges.add(challenge_id)
        self.total_points += points

    def get_unsolved_challenges(self):
        """Return challenges not yet solved"""
        return {
            cid: c for cid, c in self.challenges.items()
            if cid not in self.solved_challenges
        }

    def get_solved_challenges(self):
        """Return solved challenges"""
        return {
            cid: c for cid, c in self.challenges.items()
            if cid in self.solved_challenges
        }

    def to_dict(self):
        """Serialize player for leaderboard display"""
        return {
            'id': self.id,
            'username': self.username,
            'total_points': self.total_points,
            'challenges_solved': len(self.solved_challenges),
            'created_at': self.created_at.isoformat(),
        }
