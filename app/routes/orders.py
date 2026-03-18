"""
/orders/<order_id> — cert purchase order detail.

Intentional vulnerability: IDOR (Insecure Direct Object Reference).
Order IDs are sequential integers with no ownership check — any authenticated
user can read any order by incrementing the ID.

Order 1 belongs to svc_admin, leaking the admin username required for Step 4
(hash cracking). This is a reconnaissance step, not direct escalation.

Found via:
  - /account page lists the player's own order IDs (inviting enumeration)
  - /.git/logs/HEAD commit message mentions "add orders endpoint (sequential IDs)"
  - robots.txt Disallow: /orders/
"""
from flask import Blueprint, jsonify, session, redirect, url_for
from app.storage.memory_store import MemoryStore

bp = Blueprint('orders', __name__)


def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'player_id' not in session:
            return redirect(url_for('auth.register'))
        return f(*args, **kwargs)
    return decorated


@bp.route('/orders/<int:order_id>')
@require_login
def get_order(order_id):
    store = MemoryStore.get_instance()
    # No ownership check — any authenticated user can read any order ID
    order = store.get_order(order_id)
    if not order:
        return jsonify({"error": "Order not found", "order_id": order_id}), 404
    return jsonify(order)
