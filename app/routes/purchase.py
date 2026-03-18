"""
/purchase — cert voucher purchase handler.

Intentional vulnerability: business logic flaw + debug info leakage.

The form POSTs cert_id, quantity, and price (client-controlled).
With a negative quantity, _generate_voucher() raises a ValueError that
propagates unhandled. Flask's DEBUG=True renders the Werkzeug interactive
debugger, leaking:

  - Full traceback with source lines
  - Local variables at every frame, including `all_orders` (the full order dict,
    revealing svc_admin as order 1's customer) and `session` contents
  - Internal file paths (app/routes/purchase.py, app/storage/memory_store.py)
  - Flask version, Python version, Werkzeug version

This is realistic: Flask DEBUG=True left on in production is a standard
pentest finding. A secure site would have DEBUG=False.

Chain role: alternative reconnaissance path to IDOR — the debug traceback
exposes `all_orders` in local scope, revealing svc_admin's username without
needing to enumerate /orders/.
"""
import random
from flask import Blueprint, request, session, redirect, url_for, render_template
from app.storage.memory_store import MemoryStore

bp = Blueprint('purchase', __name__)

CERT_PRICES = {
    "a-":        219,
    "network-":  349,
    "security-": 392,
    "linux-":    338,
    "pentest-":  466,
    "cloud-":    359,
}


def _generate_voucher(cert_id: str, quantity: int, order_id: int) -> str:
    """
    Generate a voucher code for `quantity` units of `cert_id`.
    Raises ValueError for non-positive quantities.
    """
    if quantity < 1:
        raise ValueError(
            f"purchase_handler: invalid quantity={quantity!r} for cert {cert_id!r} "
            f"(pending order_id={order_id}). "
            f"Voucher generation requires quantity >= 1."
        )
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    segments = ["".join(random.choices(chars, k=4)) for _ in range(2)]
    return f"CERT-{segments[0]}-{segments[1]}"


def require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'player_id' not in session:
            return redirect(url_for('auth.register'))
        return f(*args, **kwargs)
    return decorated


@bp.route('/purchase', methods=['POST'])
@require_login
def purchase():
    cert_id  = request.form.get('cert_id', '').strip().lower()
    quantity = int(request.form.get('quantity', '1'))

    store      = MemoryStore.get_instance()
    all_orders = store.orders                           # in scope when crash occurs
    next_order_id = max(all_orders.keys(), default=0) + 1

    price_per_unit = CERT_PRICES.get(cert_id, 0)
    total          = price_per_unit * quantity          # negative if quantity < 0

    # _generate_voucher raises ValueError for quantity < 1.
    # With DEBUG=True this triggers Werkzeug's interactive debugger, leaking
    # all_orders, session, price_per_unit, total, and file paths to the browser.
    voucher = _generate_voucher(cert_id, quantity, next_order_id)

    new_order = {
        "order_id":          next_order_id,
        "customer_username": session['username'],
        "cert":              f"CeroDias {cert_id.capitalize()}",
        "quantity":          quantity,
        "total":             total,
        "voucher_code":      voucher,
        "date":              "2026-03-11",
        "status":            "issued",
    }
    store.add_order(new_order)
    return redirect(url_for('account.account'))
