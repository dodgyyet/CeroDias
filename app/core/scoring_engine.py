"""Scoring and points calculation"""


class ScoringEngine:
    """Calculate points awarded for solving challenges"""

    def __init__(self, time_penalty_per_minute=1):
        self.time_penalty_per_minute = time_penalty_per_minute

    def calculate_points(self, challenge):
        """
        Calculate points for solving a challenge.

        Formula: base_points - (minutes_elapsed * penalty_per_minute)
        Minimum: 0 points

        Args:
            challenge: Solved Challenge object

        Returns:
            int: Points earned
        """
        if not challenge.is_solved:
            return 0

        base_points = challenge.base_points
        time_elapsed_minutes = challenge.flag.time_elapsed_minutes()

        if time_elapsed_minutes is None:
            return 0

        penalty = time_elapsed_minutes * self.time_penalty_per_minute
        points = max(0, int(base_points - penalty))

        return points

    def get_time_penalty_info(self, challenge):
        """Get penalty breakdown for display"""
        time_minutes = challenge.flag.time_elapsed_minutes()
        if time_minutes is None:
            return None

        penalty = time_minutes * self.time_penalty_per_minute
        points = self.calculate_points(challenge)

        return {
            'base_points': challenge.base_points,
            'time_minutes': time_minutes,
            'penalty': penalty,
            'final_points': points,
        }
