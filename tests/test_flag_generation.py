"""Tests for flag generation"""
import pytest
from app.core.flag_generator import FlagGenerator
from app.models.flag import Flag


class TestFlagGenerator:
    """Test flag generation and variants"""

    def test_generate_flag_generic(self):
        """Test generic flag generation"""
        gen = FlagGenerator()
        flag = gen.generate_flag('generic')
        assert flag.startswith('FLAG{')
        assert flag.endswith('}')
        assert len(flag) > 10

    def test_generate_flag_password(self):
        """Test password-style flag generation"""
        gen = FlagGenerator()
        flag = gen.generate_flag('password')
        assert flag.startswith('FLAG{')
        assert '_' in flag
        assert any(c.isdigit() for c in flag)

    def test_generate_flag_api_key(self):
        """Test API key-style flag generation"""
        gen = FlagGenerator()
        flag = gen.generate_flag('api_key')
        assert flag.startswith('FLAG{')
        content = flag[5:-1]
        assert len(content) == 32

    def test_seeded_flag_reproducibility(self):
        """Test that seeded generation is reproducible"""
        gen1 = FlagGenerator(seed=12345)
        flag1 = gen1.generate_flag('password')

        gen2 = FlagGenerator(seed=12345)
        flag2 = gen2.generate_flag('password')

        assert flag1 == flag2

    def test_different_seeds_different_flags(self):
        """Test that different seeds produce different flags"""
        gen1 = FlagGenerator(seed=111)
        flag1 = gen1.generate_flag('password')

        gen2 = FlagGenerator(seed=222)
        flag2 = gen2.generate_flag('password')

        assert flag1 != flag2


class TestFlagModel:
    """Test Flag model"""

    def test_flag_creation(self):
        """Test flag object creation"""
        flag = Flag('challenge1', 'player1', 'FLAG{secret123}', 'Easy')
        assert flag.challenge_id == 'challenge1'
        assert flag.player_id == 'player1'
        assert flag.generated_flag == 'FLAG{secret123}'
        assert flag.difficulty == 'Easy'
        assert flag.submitted_at is None

    def test_flag_variants(self):
        """Test flag accepts variants"""
        flag = Flag('c1', 'p1', 'FLAG{admin_password_123}', 'Easy')
        assert flag.is_correct('FLAG{admin_password_123}')
        assert flag.is_correct('flag{admin_password_123}')  # lowercase
        assert flag.is_correct('FLAG{ADMIN_PASSWORD_123}')  # uppercase
        assert flag.is_correct('admin_password_123')  # without brackets

    def test_flag_incorrect(self):
        """Test flag rejects incorrect submissions"""
        flag = Flag('c1', 'p1', 'FLAG{correct}', 'Easy')
        assert not flag.is_correct('FLAG{wrong}')
        assert not flag.is_correct('incorrect')

    def test_flag_time_elapsed(self):
        """Test time elapsed calculation"""
        flag = Flag('c1', 'p1', 'FLAG{test}', 'Easy')
        assert flag.time_elapsed_minutes() is None
        flag.mark_solved()
        elapsed = flag.time_elapsed_minutes()
        assert elapsed is not None
        assert elapsed >= 0
