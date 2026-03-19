"""Admin routes for resetting and managing game state"""
from flask import Blueprint, render_template, request, jsonify, session
from app.storage.memory_store import MemoryStore
from app.core import leaderboard_store

bp = Blueprint('admin', __name__)
store = MemoryStore()

ADMIN_PASSWORD = 'admin'  # TODO: Change in production


@bp.route('/admin')
def admin_panel():
    """Admin panel"""
    return render_template('admin.html')


@bp.route('/admin/reset', methods=['POST'])
def reset_game():
    """Reset all game data"""
    password = request.form.get('password', '')

    if password != ADMIN_PASSWORD:
        return jsonify({'success': False, 'message': 'Invalid password'}), 401

    store.reset()
    return jsonify({'success': True, 'message': 'Game reset successfully'})


@bp.route('/admin/chain-complete', methods=['GET', 'POST'])
def chain_complete():
    """Chain completion verification and leaderboard recording"""
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
    return render_template('chain_complete.html', token=token, leaderboard=board,
                           username=leaderboard_store._sanitize_username(username),
                           elapsed=int(elapsed))


@bp.route('/admin/stats')
def admin_stats():
    """Get admin statistics"""
    return jsonify({
        'total_players': len(store.players),
        'total_challenges': len(store.challenges),
        'leaderboard_entries': len(store.leaderboard),
    })
