"""
/internal-panel — staff portal (crown jewel)

Not linked anywhere in the public UI. Discovered via:
  1. robots.txt (Disallow: /internal-panel)
  2. SSTI file read on this file
  3. Prompt injection — chatbot leaks the path from info.md internal section

Login requires: username + bcrypt-verified password + valid TOTP code.
Session forgery (Flask cookie) does not work — credentials are validated server-side.
See HACKING.md Step 6 for the full exploitation walkthrough.
"""
from flask import Blueprint, request, session, render_template

from app.storage.memory_store import MemoryStore

bp = Blueprint('internal', __name__, url_prefix='/internal-panel')


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        import bcrypt as _bcrypt
        if hashed.startswith('INSTALL'):
            return False
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except ImportError:
        return False


def _verify_totp(seed: str, code: str) -> bool:
    try:
        import pyotp
        return pyotp.TOTP(seed).verify(code, valid_window=1)
    except Exception:
        return False


def _get_totp_seed(username: str) -> str:
    """Decrypt the stored TOTP seed for a user (requires pycryptodome)."""
    try:
        import hashlib, base64
        from Crypto.Cipher import AES
        from flask import current_app

        secret_key = current_app.config.get('SECRET_KEY', '')
        store = MemoryStore.get_instance()
        user = next((u for u in store.get_user_table() if u['username'] == username), None)
        if not user or not user.get('encrypted_totp_seed'):
            return ''

        key = hashlib.md5((secret_key + username).encode()).digest()
        ciphertext = base64.b64decode(user['encrypted_totp_seed'])
        seed = AES.new(key, AES.MODE_ECB).decrypt(ciphertext).rstrip(b'\x00').decode()
        return seed
    except Exception:
        return ''


@bp.route('/', methods=['GET'])
def panel_login():
    return render_template('internal_panel.html')


@bp.route('/', methods=['POST'])
def panel_authenticate():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    otp_code = request.form.get('otp', '').strip()

    store = MemoryStore.get_instance()
    user = next((u for u in store.get_user_table() if u['username'] == username), None)

    if not user:
        return render_template('internal_panel.html', error='Invalid credentials'), 401

    if not _verify_password(password, user['bcrypt_hash']):
        return render_template('internal_panel.html', error='Invalid credentials'), 401

    seed = _get_totp_seed(username)
    if not seed or not _verify_totp(seed, otp_code):
        return render_template('internal_panel.html', error='Invalid OTP'), 401

    session['internal_admin'] = username
    session['internal_role'] = user['role']
    return render_template('internal_panel_home.html',
                           user=user,
                           players=list(store.players.values()),
                           challenges=list(store.challenges.values()))
