"""
/account — customer portal for registered users (Tier 2).

Registered users land here after sign-up. Shows cert purchase history with
sequential order IDs — the enumerable surface for the IDOR on /orders/<id>.
"""
from flask import Blueprint, render_template, session, redirect, url_for
from app.core.session_manager import SessionManager
from app.storage.memory_store import MemoryStore

bp = Blueprint('account', __name__)
session_manager = SessionManager()


def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'player_id' not in session:
            return redirect(url_for('auth.register'))
        return f(*args, **kwargs)
    return decorated


@bp.route('/account')
@require_login
def account():
    player_id = session['player_id']
    username = session['username']
    store = MemoryStore.get_instance()

    # Find orders belonging to this player
    my_orders = [o for o in store.orders.values() if o['customer_username'] == username]
    my_orders.sort(key=lambda o: o['order_id'])

    # If brand-new account with no orders, seed one welcome order
    if not my_orders:
        import random, string
        next_id = max(store.orders.keys(), default=0) + 1
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        code = "CERT-" + "".join(random.choices(chars, k=4)) + "-" + "".join(random.choices(chars, k=4))
        welcome_order = {
            "order_id": next_id,
            "customer_username": username,
            "cert": "CeroDias A-",
            "quantity": 1,
            "total": 219,
            "voucher_code": code,
            "date": "2026-03-11",
            "status": "issued",
        }
        store.add_order(welcome_order)
        my_orders = [welcome_order]

    return render_template('account.html', username=username, orders=my_orders)
