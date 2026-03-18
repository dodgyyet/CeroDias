"""Flag submission routes"""
from flask import Blueprint, request, jsonify, session
from app.storage.memory_store import MemoryStore
from app.core.scoring_engine import ScoringEngine

bp = Blueprint('submit', __name__)
store = MemoryStore()
scoring_engine = ScoringEngine()


@bp.route('/submit', methods=['POST'])
def submit_flag():
    """Submit and validate a flag"""
    if 'player_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401

    player_id = session.get('player_id')
    challenge_id = request.form.get('challenge_id')
    submitted_flag = request.form.get('flag', '').strip()

    if not challenge_id or not submitted_flag:
        return jsonify({'success': False, 'message': 'Missing challenge_id or flag'}), 400

    challenge = store.get_challenge(challenge_id)
    if not challenge:
        return jsonify({'success': False, 'message': 'Challenge not found'}), 404

    if challenge.player_id != player_id:
        return jsonify({'success': False, 'message': 'Not your challenge'}), 403

    if challenge.is_solved:
        return jsonify({'success': False, 'message': 'Already solved'}), 400

    # Validate flag
    is_correct, message = challenge.flag.is_correct(submitted_flag), None
    if is_correct:
        challenge.mark_solved()
        points = scoring_engine.calculate_points(challenge)
        player = store.get_player(player_id)
        player.solve_challenge(challenge_id, points)

        return jsonify({
            'success': True,
            'message': f'Correct! You earned {points} points',
            'points': points
        })
    else:
        return jsonify({'success': False, 'message': 'Incorrect flag'}), 400
