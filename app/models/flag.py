from datetime import datetime
import uuid


class Flag:
    def __init__(self, challenge_id, player_id, generated_flag, difficulty='Easy'):
        self.id = str(uuid.uuid4())
        self.challenge_id = challenge_id
        self.player_id = player_id
        self.generated_flag = generated_flag
        self.acceptable_flags = self._generate_variants(generated_flag)
        self.created_at = datetime.utcnow()
        self.submitted_at = None
        self.difficulty = difficulty

    @staticmethod
    def _generate_variants(flag):
        """Generate acceptable flag variants (case-insensitive, bracket variants)"""
        variants = set()
        variants.add(flag)
        variants.add(flag.lower())
        variants.add(flag.upper())
        # Remove FLAG{ } and accept just the content
        if flag.startswith('FLAG{') and flag.endswith('}'):
            content = flag[5:-1]
            variants.add(content)
            variants.add(content.lower())
        return list(variants)

    def is_correct(self, submitted_flag):
        """Check if submitted flag matches any acceptable variant"""
        return submitted_flag.strip() in self.acceptable_flags

    def mark_solved(self):
        """Mark flag as submitted/solved"""
        self.submitted_at = datetime.utcnow()

    def time_elapsed_minutes(self):
        """Return minutes since flag creation"""
        if self.submitted_at:
            delta = self.submitted_at - self.created_at
            return delta.total_seconds() / 60
        return None
