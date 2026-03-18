from datetime import datetime
import uuid


class Challenge:
    def __init__(self, vulnerability_type, difficulty, player_id, flag, vulnerable_code, base_points, parameters=None):
        self.id = str(uuid.uuid4())
        self.vulnerability_type = vulnerability_type
        self.difficulty = difficulty
        self.player_id = player_id
        self.flag = flag
        self.vulnerable_code = vulnerable_code
        self.base_points = base_points
        self.parameters = parameters or {}
        self.created_at = datetime.utcnow()
        self.is_solved = False
        self.solved_at = None

    def mark_solved(self):
        """Mark challenge as solved"""
        self.is_solved = True
        self.solved_at = datetime.utcnow()
        self.flag.mark_solved()

    def to_dict(self):
        """Serialize challenge for display"""
        return {
            'id': self.id,
            'vulnerability_type': self.vulnerability_type,
            'difficulty': self.difficulty,
            'vulnerable_code': self.vulnerable_code,
            'base_points': self.base_points,
            'is_solved': self.is_solved,
            'created_at': self.created_at.isoformat(),
        }
