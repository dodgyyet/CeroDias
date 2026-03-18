"""
/messages — internal staff inbox.

Requires a staff session (role: staff). Regular customer sessions get 403.
j.harris's inbox contains the k.chen DM — the chain alternative path.

Accessible to any logged-in user (returns 403 for non-staff), so a player who
discovers this route before cracking j.harris will learn the endpoint exists
but cannot read the messages. This is intentional — the 403 tells them they
need a staff account.
"""
from flask import Blueprint, render_template, session, abort, redirect, url_for

bp = Blueprint('messages', __name__)


@bp.route('/messages')
def messages():
    if 'player_id' not in session:
        return redirect(url_for('auth.register'))
    if session.get('role') != 'staff':
        abort(403)

    from app.storage.memory_store import MemoryStore
    store = MemoryStore.get_instance()
    username = session['username']
    inbox = [m for m in store.staff_messages if m['recipient'] == username]
    return render_template('messages.html', username=username, inbox=inbox)
