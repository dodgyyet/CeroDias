"""Challenge display routes"""
from flask import Blueprint, render_template, session, redirect, url_for, request
from app.core.session_manager import SessionManager

bp = Blueprint('challenges', __name__)
session_manager = SessionManager()


def require_login(f):
    """Decorator to require login"""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'player_id' not in session:
            return redirect(url_for('auth.register'))
        return f(*args, **kwargs)

    return decorated_function


@bp.route('/challenge/<vuln_type>/<difficulty>')
@require_login
def get_challenge(vuln_type, difficulty):
    """Get a challenge for the player"""
    player_id = session.get('player_id')
    username = session.get('username')

    try:
        challenge = session_manager.assign_challenge(player_id, vuln_type, difficulty)

        return render_template(
            'challenge.html',
            challenge=challenge,
            username=username,
            challenge_id=challenge.id,
            vulnerability_type=vuln_type,
            difficulty=difficulty
        )
    except ValueError as e:
        return render_template('error.html', error=str(e)), 400


@bp.route('/challenges/available')
@require_login
def list_available():
    """List available challenges"""
    player_id = session.get('player_id')
    username = session.get('username')

    player = session_manager.get_player(player_id)
    if not player:
        return redirect(url_for('auth.register'))

    # For MVP: Show SQL Injection Easy and Medium
    available = [
        {'type': 'sql_injection', 'difficulty': 'Easy', 'points': 100},
        {'type': 'sql_injection', 'difficulty': 'Medium', 'points': 150},
    ]

    return render_template(
        'challenges.html',
        available_challenges=available,
        solved_challenges=list(player.solved_challenges),
        username=username
    )
