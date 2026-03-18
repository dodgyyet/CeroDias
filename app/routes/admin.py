"""Admin routes for resetting and managing game state"""
from flask import Blueprint, render_template, request, redirect, url_for, jsonify
from app.storage.memory_store import MemoryStore

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


@bp.route('/admin/stats')
def admin_stats():
    """Get admin statistics"""
    return jsonify({
        'total_players': len(store.players),
        'total_challenges': len(store.challenges),
        'leaderboard_entries': len(store.leaderboard),
    })
