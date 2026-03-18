"""Flag generation with randomization and seeding"""
import random
import string


class FlagGenerator:
    """Generate random flags with optional seeding for reproducibility"""

    def __init__(self, seed=None):
        self.seed = seed
        if seed is not None:
            random.seed(seed)

    def generate_flag(self, flag_type='generic', params=None):
        """
        Generate a flag for a challenge.

        Args:
            flag_type: Type of flag ('generic', 'password', 'api_key', etc.)
            params: Optional dict with customization parameters

        Returns:
            str: Generated flag in format FLAG{content}
        """
        params = params or {}

        if flag_type == 'password':
            content = self._generate_password()
        elif flag_type == 'api_key':
            content = self._generate_api_key()
        elif flag_type == 'token':
            content = self._generate_token()
        else:
            content = self._generate_generic()

        return f"FLAG{{{content}}}"

    @staticmethod
    def _generate_password():
        """Generate a random password-like string"""
        adjectives = [
            'admin', 'super', 'secret', 'hidden', 'special',
            'ultimate', 'master', 'root', 'backup', 'legacy'
        ]
        nouns = [
            'password', 'pass', 'pwd', 'secret', 'credential',
            'auth', 'token', 'key', 'hash', 'code'
        ]
        suffix = ''.join(random.choices(string.digits, k=3))
        return f"{random.choice(adjectives)}_{random.choice(nouns)}_{suffix}"

    @staticmethod
    def _generate_api_key():
        """Generate a random API key-like string"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=32))

    @staticmethod
    def _generate_token():
        """Generate a random token-like string"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=24))

    @staticmethod
    def _generate_generic():
        """Generate a generic random flag content"""
        return ''.join(random.choices(string.ascii_letters + string.digits + '_', k=16))
