"""Dashboard and leaderboard routes — Tier 3 (admin only).

/dashboard and /leaderboard are not linked from the public site.
They require session['internal_admin'] to be set, which only happens
after successfully logging into /internal-panel with valid credentials + TOTP.

A normal registered user hitting /dashboard is redirected to /account.
"""
from flask import Blueprint, render_template, session, redirect, url_for
from app.core.session_manager import SessionManager

bp = Blueprint('dashboard', __name__)
session_manager = SessionManager()


def require_admin(f):
    """Require internal-panel admin session (Tier 3)."""
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('internal_admin'):
            if session.get('player_id'):
                return redirect(url_for('account.account'))
            return redirect(url_for('auth.register'))
        return f(*args, **kwargs)

    return decorated_function


@bp.route('/dashboard')
@require_admin
def dashboard():
    """CTF challenge dashboard — only reachable after /internal-panel login."""
    player_id = session.get('player_id')
    username = session.get('internal_admin')

    # Admin may not have a player entry — use svc_admin stub if needed
    player = session_manager.get_player(player_id) if player_id else None
    if not player:
        from app.models.player import Player
        player = Player.__new__(Player)
        player.id = 'admin'
        player.username = username
        player.total_points = 0
        player.solved_challenges = []

    leaderboard = session_manager.store.get_leaderboard()

    return render_template(
        'dashboard.html',
        username=username,
        player=player,
        leaderboard=leaderboard,
        active_challenges=session_manager.get_active_challenges(player_id) if player_id else [],
        solved_challenges=session_manager.get_solved_challenges(player_id) if player_id else [],
    )


@bp.route('/leaderboard')
@require_admin
def leaderboard():
    """Leaderboard — only reachable after /internal-panel login."""
    lb = session_manager.store.get_leaderboard()
    return render_template('leaderboard.html', leaderboard=lb)
