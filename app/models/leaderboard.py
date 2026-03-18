from datetime import datetime


class LeaderboardEntry:
    def __init__(self, player_id, username, total_points, challenges_solved):
        self.player_id = player_id
        self.username = username
        self.total_points = total_points
        self.challenges_solved = challenges_solved
        self.time_of_last_solve = datetime.utcnow()

    def to_dict(self):
        return {
            'player_id': self.player_id,
            'username': self.username,
            'total_points': self.total_points,
            'challenges_solved': self.challenges_solved,
            'time_of_last_solve': self.time_of_last_solve.isoformat(),
        }
