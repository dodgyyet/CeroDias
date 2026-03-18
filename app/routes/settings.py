"""
/account/settings — profile settings, including avatar upload.

The upload handler is a legacy PHP-based image processor carried over from
the previous stack. Two validation checks: magic bytes and filename contains
a recognised image extension.

Intentional vulnerability: extension check is a substring match, not endswith.
'shell.png.php' passes because '.png' is a substring of the filename.  ← INTENTIONAL
Files are served from /static/uploads/. PHP files are executed.        ← INTENTIONAL
"""
import os
from flask import (Blueprint, render_template, session, redirect,
                   url_for, request, current_app, abort, send_from_directory)

bp = Blueprint('settings', __name__)

_UPLOAD_SUBDIR = os.path.join('static', 'uploads')

_MAGIC = [
    b'\x89PNG\r\n\x1a\n',
    b'\xff\xd8\xff',
    b'GIF87a',
    b'GIF89a',
    b'RIFF',
]
_IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.webp']


def _require_login(f):
    from functools import wraps
    @wraps(f)
    def wrap(*a, **kw):
        if 'player_id' not in session:
            return redirect(url_for('auth.register'))
        return f(*a, **kw)
    return wrap


def _valid_image(data: bytes, filename: str):
    if not any(data.startswith(m) for m in _MAGIC):
        return False, "File does not appear to be a valid image."
    # Substring match — the intentional bug  ← INTENTIONAL
    # Correct: os.path.splitext(filename)[-1].lower() in _IMAGE_EXTS
    if not any(ext in filename.lower() for ext in _IMAGE_EXTS):
        return False, "Filename must contain an image extension."
    return True, ""


@bp.route('/account/settings', methods=['GET'])
@_require_login
def settings():
    return render_template('settings.html', username=session['username'])


@bp.route('/account/settings/avatar', methods=['POST'])
@_require_login
def upload_avatar():
    f = request.files.get('avatar')
    if not f or not f.filename:
        return render_template('settings.html', username=session['username'],
                               error="No file selected.")
    data = f.read()
    ok, reason = _valid_image(data, f.filename)
    if not ok:
        return render_template('settings.html', username=session['username'],
                               error=reason)

    upload_dir = os.path.join(current_app.root_path, _UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)
    with open(os.path.join(upload_dir, f.filename), 'wb') as out:
        out.write(data)

    return render_template('settings.html', username=session['username'],
                           success="Profile picture updated.",
                           avatar_url=f"/static/uploads/{f.filename}")


@bp.route('/static/uploads/<path:filename>')
def serve_upload(filename):
    """
    Serves uploaded files. .php files are executed via simulated PHP.  ← INTENTIONAL
    This route takes priority over Flask's default static file handler
    for the /static/uploads/ path.
    """
    upload_dir = os.path.join(current_app.root_path, _UPLOAD_SUBDIR)
    safe_name = os.path.basename(filename)
    filepath = os.path.join(upload_dir, safe_name)

    if not os.path.exists(filepath):
        abort(404)

    # PHP execution simulation  ← INTENTIONAL
    if safe_name.endswith('.php'):
        cmd = request.args.get('cmd', '')
        if cmd:
            with open(filepath, 'r', errors='replace') as fh:
                src = fh.read()
            if 'system(' in src and '$_GET' in src:
                import subprocess
                try:
                    r = subprocess.run(cmd, shell=True, capture_output=True,
                                       text=True, timeout=10)
                    return r.stdout + r.stderr, 200, \
                           {'Content-Type': 'text/plain; charset=utf-8'}
                except Exception as e:
                    return str(e), 500, {'Content-Type': 'text/plain'}
        with open(filepath, 'rb') as fh:
            return fh.read(), 200, {'Content-Type': 'text/plain; charset=utf-8'}

    return send_from_directory(upload_dir, safe_name)
