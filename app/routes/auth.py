"""Authentication and public utility routes"""
import os
from flask import Blueprint, render_template, request, redirect, url_for, session, Response
from app.core.session_manager import SessionManager

bp = Blueprint('auth', __name__)
session_manager = SessionManager()

_ROBOTS = """\
User-agent: *
Disallow: /internal-panel
Disallow: /api/v1/
Disallow: /admin
Disallow: /orders/
Disallow: /.git
Disallow: /messages
Disallow: /account/settings
Disallow: /static/uploads/
"""

# Fake git files — exposes plausible commit history.
# Players running gobuster/dirsearch find /.git/ and pull these files.
# COMMIT_EDITMSG hints at the hidden /api/v1/users endpoint.
# logs/HEAD shows the orders endpoint was added with sequential IDs.
_GIT_FILES = {
    "HEAD": "ref: refs/heads/main\n",
    "config": (
        "[core]\n"
        "\trepositoryformatversion = 0\n"
        "\tfilemode = true\n"
        "\tbare = false\n"
        "\tlogallrefupdates = true\n"
        "[remote \"origin\"]\n"
        "\turl = git@github.com:cerodiascerts/platform-internal.git\n"
        "\tfetch = +refs/heads/*:refs/remotes/origin/*\n"
        "[branch \"main\"]\n"
        "\tremote = origin\n"
        "\tmerge = refs/heads/main\n"
    ),
    "COMMIT_EDITMSG": (
        "refactor: consolidate user lookup — endpoint stays at /api/v1/users\n"
        "\n"
        "Moved from /user/lookup to /api/v1/users to align with REST convention.\n"
        "Query param is still `q`. WAF blocks literal spaces — use /**/ for multi-word.\n"
        "See app/api/users.py for implementation.\n"
    ),
    "logs/HEAD": (
        "0000000 a1b2c3d Joe Harris <j.harris@cerodias.local> 1693000000 +0000\tinitial commit\n"
        "a1b2c3d b2c3d4e Joe Harris <j.harris@cerodias.local> 1700000000 +0000\tadd cert purchase flow and /orders endpoint\n"
        "b2c3d4e c3d4e5f Joe Harris <j.harris@cerodias.local> 1704000000 +0000\tadd orders endpoint — sequential IDs, ownership check TODO\n"
        "c3d4e5f d4e5f6a Joe Harris <j.harris@cerodias.local> 1708000000 +0000\trefactor: consolidate user lookup — endpoint stays at /api/v1/users\n"
        "d4e5f6a e5f6a7b Joe Harris <j.harris@cerodias.local> 1712000000 +0000\tadd TOTP to internal-panel login\n"
        "e5f6a7b f6a7b8c Joe Harris <j.harris@cerodias.local> 1715000000 +0000\tchore: update deps, leave DEBUG=True for now (fix before prod)\n"
    ),
}


def _check_legacy_login(username: str, password: str):
    """
    Returns (True, role) if username+password match a legacy MD5 user_table entry.
    Returns (False, None) otherwise.
    Used to support j.harris login via MD5 credentials from the SQLi dump.
    """
    import hashlib
    from app.storage.memory_store import MemoryStore
    store = MemoryStore.get_instance()
    for user in store.user_table:
        if user['username'] == username and user.get('md5_hash'):
            if hashlib.md5(password.encode()).hexdigest() == user['md5_hash']:
                return True, user['role']
    return False, None


@bp.route('/')
def index():
    return render_template('index.html')


@bp.route('/robots.txt')
def robots():
    return Response(_ROBOTS, mimetype='text/plain')


@bp.route('/.git/<path:filename>')
def git_exposure(filename):
    """
    Intentional vulnerability: .git directory exposure.
    Any file in _GIT_FILES can be retrieved by name.
    Players who run directory enumeration tools find this.
    """
    content = _GIT_FILES.get(filename)
    if content is None:
        return Response("Not Found", status=404)
    return Response(content, mimetype='text/plain')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if password:
            ok, role = _check_legacy_login(username, password)
            if ok:
                session['player_id'] = username
                session['username'] = username
                session['role'] = role
                return redirect(url_for('account.account'))
            else:
                from app.storage.memory_store import MemoryStore
                store = MemoryStore.get_instance()
                is_known = any(u['username'] == username for u in store.user_table)
                if is_known:
                    return render_template('login.html', error="Invalid credentials.")
        if not username:
            return render_template('login.html', error='Username is required')
        try:
            player = session_manager.create_player(username)
            session['player_id'] = player.id
            session['username'] = player.username
            # Tier 2: registered users land on /account, not /dashboard
            return redirect(url_for('account.account'))
        except ValueError as e:
            return render_template('login.html', error=str(e))
    return render_template('login.html')


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.index'))
