"""Chain completion endpoint — the final payoff after root."""
from flask import Blueprint, render_template, request, session
from app.core import leaderboard_store

bp = Blueprint('admin', __name__)


@bp.route('/chain-complete', methods=['GET', 'POST'])
def chain_complete():
    """Verify the admin_token found at /root/.cerodias/admin_token and record completion."""
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        token = data.get('token', '')
    else:
        token = request.args.get('token', '')

    if not leaderboard_store.validate_token(token):
        return '', 404

    username = session.get('username', 'anonymous')
    elapsed = session.get('elapsed_seconds', 0)
    attempts = session.get('chain_attempts', {})
    leaderboard_store.record_completion(username, elapsed, attempts)

    board = leaderboard_store.get_leaderboard()
    return render_template(
        'chain_complete.html',
        token=token,
        leaderboard=board,
        username=leaderboard_store.sanitize_username(username),
        elapsed=int(elapsed),
    )
