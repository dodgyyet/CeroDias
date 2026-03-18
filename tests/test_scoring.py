"""Tests for scoring engine"""
import pytest
from datetime import datetime, timedelta
from app.core.scoring_engine import ScoringEngine
from app.models.flag import Flag
from app.models.challenge import Challenge
from app.core.vulnerability_registry import VulnerabilityRegistry


class TestScoringEngine:
    """Test scoring calculations"""

    def test_unsolved_challenge_zero_points(self):
        """Test unsolved challenge awards zero points"""
        engine = ScoringEngine()
        flag = Flag('c1', 'p1', 'FLAG{test}', 'Easy')
        challenge = Challenge('sql_injection', 'Easy', 'p1', flag, 'code', 100)

        points = engine.calculate_points(challenge)
        assert points == 0

    def test_immediate_solve_full_points(self):
        """Test immediate solution awards full points"""
        engine = ScoringEngine()
        flag = Flag('c1', 'p1', 'FLAG{test}', 'Easy')
        challenge = Challenge('sql_injection', 'Easy', 'p1', flag, 'code', 100)

        # Mark solved immediately
        challenge.mark_solved()

        points = engine.calculate_points(challenge)
        # Should be around 100 (minus small time penalty)
        assert points >= 99

    def test_points_decrease_with_time(self):
        """Test points decrease based on time spent"""
        engine = ScoringEngine(time_penalty_per_minute=1)

        flag1 = Flag('c1', 'p1', 'FLAG{test}', 'Easy')
        challenge1 = Challenge('sql_injection', 'Easy', 'p1', flag1, 'code', 100)
        challenge1.mark_solved()
        points1 = engine.calculate_points(challenge1)

        # Simulate 5 minutes passing
        flag2 = Flag('c2', 'p2', 'FLAG{test2}', 'Easy')
        challenge2 = Challenge('sql_injection', 'Easy', 'p2', flag2, 'code', 100)
        challenge2.flag.created_at = datetime.utcnow() - timedelta(minutes=5)
        challenge2.mark_solved()
        points2 = engine.calculate_points(challenge2)

        assert points2 < points1
        assert points2 <= 95  # 100 - (5 * 1), allow small variance

    def test_points_minimum_zero(self):
        """Test points never go below zero"""
        engine = ScoringEngine(time_penalty_per_minute=10)

        flag = Flag('c1', 'p1', 'FLAG{test}', 'Easy')
        challenge = Challenge('sql_injection', 'Easy', 'p1', flag, 'code', 100)
        challenge.flag.created_at = datetime.utcnow() - timedelta(minutes=20)
        challenge.mark_solved()

        points = engine.calculate_points(challenge)
        assert points >= 0

    def test_penalty_info_display(self):
        """Test penalty info calculation"""
        engine = ScoringEngine(time_penalty_per_minute=1)

        flag = Flag('c1', 'p1', 'FLAG{test}', 'Medium')
        challenge = Challenge('sql_injection', 'Medium', 'p1', flag, 'code', 150)
        challenge.flag.created_at = datetime.utcnow() - timedelta(minutes=3)
        challenge.mark_solved()

        info = engine.get_time_penalty_info(challenge)
        assert info is not None
        assert info['base_points'] == 150
        assert info['time_minutes'] == pytest.approx(3, abs=0.1)
        assert info['penalty'] == pytest.approx(3, abs=0.1)
        assert info['final_points'] == pytest.approx(147, abs=1)
