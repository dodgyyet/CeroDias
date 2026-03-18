"""Challenge generation and validation"""
import random
from app.core.vulnerability_registry import VulnerabilityRegistry
from app.core.flag_generator import FlagGenerator
from app.models.flag import Flag
from app.models.challenge import Challenge


class ChallengeEngine:
    """Generate and manage challenges for players"""

    def __init__(self, seed=None):
        self.registry = VulnerabilityRegistry()
        self.flag_generator = FlagGenerator(seed=seed)
        self.seed = seed

    def generate_challenge(self, player_id, vuln_type, difficulty):
        """
        Generate a new challenge for a player.

        Args:
            player_id: Player ID
            vuln_type: Vulnerability type (e.g., 'sql_injection')
            difficulty: Difficulty level ('Easy', 'Medium')

        Returns:
            Challenge object
        """
        vuln = self.registry.get_vulnerability(vuln_type)
        if not vuln:
            raise ValueError(f"Unknown vulnerability type: {vuln_type}")

        # Randomize parameters for this challenge
        randomization_config = vuln.get_randomization_config()
        params = {
            'table_name': random.choice(randomization_config.get('table_names', [])),
            'column_name': random.choice(randomization_config.get('column_names', [])),
            'difficulty': difficulty,
        }

        # Generate flag
        flag_content = self.flag_generator.generate_flag('password')
        flag = Flag(
            challenge_id=None,  # Will be set after Challenge creation
            player_id=player_id,
            generated_flag=flag_content,
            difficulty=difficulty
        )

        # Generate vulnerable code
        vulnerable_code = vuln.generate_vulnerable_code(params)

        # Get base points for difficulty
        difficulty_info = vuln.get_difficulty_info(difficulty)
        base_points = difficulty_info['base_points']

        # Create challenge
        challenge = Challenge(
            vulnerability_type=vuln_type,
            difficulty=difficulty,
            player_id=player_id,
            flag=flag,
            vulnerable_code=vulnerable_code,
            base_points=base_points,
            parameters=params
        )

        flag.challenge_id = challenge.id

        return challenge

    def validate_flag(self, challenge, submitted_flag):
        """
        Validate a submitted flag against a challenge.

        Args:
            challenge: Challenge object
            submitted_flag: Player's submitted flag string

        Returns:
            tuple: (is_correct: bool, message: str)
        """
        if challenge.is_solved:
            return False, "Challenge already solved!"

        if challenge.flag.is_correct(submitted_flag):
            challenge.mark_solved()
            return True, "Correct! Flag accepted."
        else:
            return False, "Incorrect flag. Try again."
