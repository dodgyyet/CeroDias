# CeroDias — Chain Implementation Plan

Read `story.md` and `HACKING.md` before implementing anything. This document defines
the full attack chain and splits implementation across four agents that can run
concurrently after Agent A finishes.

**Do not fix intentional vulnerabilities.** Anything marked `← INTENTIONAL` must
be implemented exactly as described, including the bug.

---

## Attack Chain Overview

```
Recon  →  robots.txt, .git/COMMIT_EDITMSG, IDOR /orders/1
           Yields: svc_admin username, /api/v1/users endpoint name

SSTI   →  /search?q={{...}}
           Read app/api/users.py  → SQLi endpoint + dev comment (MD5 migration, staff_messages table)
           Read app/logs/deploy.log → passphrase file location (/var/cerodias/deploy.key)

SQLi   →  /api/v1/users?q=...
           OR injection  → user table: svc_admin encrypted_ssh_key blob + j.harris MD5 hash
           UNION inject  → staff_messages table → k.chen DM (confirms blob, names passphrase path)

RCE    →  upload shell.png.php (valid PNG magic bytes, Burp intercept to rename)
           GET /static/uploads/shell.png.php?cmd=cat /var/cerodias/deploy.key
           Yields: AES passphrase

Decrypt → base64_decode(blob) | openssl enc -d -aes-256-cbc -pbkdf2 -k <passphrase>
           Yields: svc_admin RSA private key

SSH    →  ssh -i id_rsa svc_admin@<server>   [Docker — future]

SUID   →  local privesc → root               [Docker — future]
```

**Why every step is required:**
- SSTI: only way to find the SQLi endpoint and the passphrase file path
- SQLi: only way to get the encrypted blob (in the DB) and the k.chen message
- RCE: only way to read the passphrase off the server filesystem
- Without all three, decryption is impossible

**Parallel path (alternative, same result):**
SQLi OR injection → j.harris MD5 hash → crack (rockyou, instant) → login as j.harris
→ `/messages` UI → same k.chen DM. Both paths go through SQLi.

---

## Agent Dependency Graph

```
Agent A  (data + docs)
    ├── completes first
    └── unblocks Agents B, C, D (run concurrently after A)

Agent B  (SQLi extension)     — no conflict with C or D
Agent C  (PHP upload + RCE)   — no conflict with B or D
Agent D  (auth + messages)    — no conflict with B or C
                                 owns: account.html, robots.txt
```

---

## Agent A — Data Layer + Documentation

**Must complete before B, C, D start.**
**Owns:** `memory_store.py`, `app/__init__.py`, `app/logs/deploy.log`,
`app/data/info.md`, `requirements.txt`, `HACKING.md`

### A1 — Update `app/storage/memory_store.py`

**`_build_user_table()`** — replace the existing function entirely:

```python
def _build_user_table():
    import hashlib as _hashlib
    try:
        import bcrypt as _bcrypt
        import base64 as _base64
        from Crypto.Cipher import AES as _AES

        def _bhash(pw):
            return _bcrypt.hashpw(pw.encode(), _bcrypt.gensalt(12)).decode()

        return [
            {
                "id": 1,
                "username": "svc_admin",
                "role": "admin",
                "bcrypt_hash": _bhash("admin_2023_root!"),
                "encrypted_ssh_key": None,   # populated at startup by _seed_ssh_key
                "md5_hash": None,
            },
            {
                "id": 2,
                "username": "j.harris",
                "role": "staff",
                "bcrypt_hash": None,
                "encrypted_ssh_key": None,
                # Legacy MD5 — migration to bcrypt pending (CERODIAS-431)  ← INTENTIONAL
                "md5_hash": _hashlib.md5("ranger".encode()).hexdigest(),
            },
        ]
    except ImportError:
        return [
            {"id": 1, "username": "svc_admin", "role": "admin",
             "bcrypt_hash": "INSTALL_BCRYPT", "encrypted_ssh_key": None, "md5_hash": None},
            {"id": 2, "username": "j.harris", "role": "staff",
             "bcrypt_hash": None, "encrypted_ssh_key": None,
             "md5_hash": "INSTALL_BCRYPT"},
        ]
```

**Add `_build_staff_messages()`** (new function, place near `_build_user_table`):

```python
def _build_staff_messages():
    """
    Internal staff DMs stored alongside user data.
    Readable via SQLi UNION injection on /api/v1/users.  ← INTENTIONAL
    The k.chen → j.harris thread is the chain pivot:
    it confirms what the encrypted_ssh_key blob is and where the passphrase lives.
    """
    return [
        {
            "id": 1,
            "sender": "k.chen",
            "recipient": "j.harris",
            "sent_at": "2024-11-15 09:03",
            "subject": "svc_admin key",
            "body": (
                "Harris — encrypted the svc_admin private key, blob is stored "
                "in their user profile in the DB (encrypted_ssh_key field). "
                "Used AES-256-CBC with pbkdf2. Passphrase is sitting at "
                "/var/cerodias/deploy.key on the server. Pull it when you can "
                "and confirm. Will clean up the passphrase file after. — K"
            ),
        },
        {
            "id": 2,
            "sender": "j.harris",
            "recipient": "k.chen",
            "sent_at": "2024-11-15 11:47",
            "subject": "Re: svc_admin key",
            "body": "Got it, pulled. All good.",
        },
    ]
```

**Add `staff_messages` to `MemoryStore.__init__`:**

```python
self.staff_messages = _build_staff_messages()
```

Place it alongside the other `self.*` assignments in `__init__`.

### A2 — Update `app/__init__.py`

Add the `_seed_ssh_key` function (before `create_app`) and call it inside `create_app`:

```python
def _seed_ssh_key(store):
    """
    Generates svc_admin RSA 2048-bit key pair at startup.
    Encrypts private key with AES-256-CBC pbkdf2 (passphrase: cerodias-deploy-2024).
    Stores encrypted blob in svc_admin's user_table row.
    Writes passphrase to /var/cerodias/deploy.key (RCE target in chain step 4).
    Writes public key to /tmp/cerodias/id_rsa.pub (for future Docker SSH setup).
    Skips if blob is already populated.
    """
    import os, subprocess, tempfile, base64

    user = next((u for u in store.user_table if u['username'] == 'svc_admin'), None)
    if user and user.get('encrypted_ssh_key'):
        return  # already seeded

    passphrase = 'cerodias-deploy-2024'

    # Write passphrase to server filesystem (the RCE target)
    for key_dir in ['/var/cerodias', '/tmp/cerodias']:
        try:
            os.makedirs(key_dir, exist_ok=True)
            with open(os.path.join(key_dir, 'deploy.key'), 'w') as f:
                f.write(passphrase)
            break
        except PermissionError:
            continue

    # Generate RSA key pair
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSH,
            encryption_algorithm=serialization.NoEncryption(),
        )
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.OpenSSH,
            format=serialization.PublicFormat.OpenSSH,
        )
    except ImportError:
        return  # cryptography package not installed

    # Encrypt private key via openssl (matches the command shown in deploy.log)
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pem') as f:
            f.write(private_pem)
            tmp_pem = f.name
        with tempfile.NamedTemporaryFile(delete=False, suffix='.enc') as f:
            tmp_enc = f.name
        subprocess.run(
            ['openssl', 'enc', '-aes-256-cbc', '-pbkdf2',
             '-k', passphrase, '-in', tmp_pem, '-out', tmp_enc],
            check=True, capture_output=True,
        )
        with open(tmp_enc, 'rb') as f:
            encrypted_bytes = f.read()
        os.unlink(tmp_pem)
        os.unlink(tmp_enc)
        encrypted_b64 = base64.b64encode(encrypted_bytes).decode()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return  # openssl not available

    if user:
        user['encrypted_ssh_key'] = encrypted_b64

    # Public key for future Docker SSH setup
    pub_dir = '/tmp/cerodias'
    os.makedirs(pub_dir, exist_ok=True)
    with open(os.path.join(pub_dir, 'id_rsa.pub'), 'wb') as f:
        f.write(public_pem)
```

Inside `create_app`, after registering existing blueprints, add:

```python
from app.routes import settings, messages
app.register_blueprint(settings.bp)
app.register_blueprint(messages.bp)

from app.storage.memory_store import MemoryStore
_seed_ssh_key(MemoryStore.get_instance())
```

### A3 — Create `app/logs/deploy.log`

Create the directory `app/logs/` and the file `app/logs/deploy.log` with this exact
content (committed to the repo, static file):

```
[2024-09-12 08:14:03] INFO  deploy: packaging release v2.3.0
[2024-09-12 08:14:08] INFO  deploy: running pre-deploy checks — ok
[2024-09-12 08:15:44] INFO  deploy: v2.3.0 deployed to production
[2024-10-28 14:02:17] INFO  deploy: packaging release v2.4.0
[2024-10-28 14:02:23] INFO  deploy: running pre-deploy checks — ok
[2024-10-28 14:03:51] INFO  deploy: v2.4.0 deployed to production
[2024-11-14 16:21:58] INFO  key_transfer: rotating svc_admin SSH key
[2024-11-14 16:22:04] INFO  key_transfer: new key pair generated
[2024-11-14 16:22:09] INFO  key_transfer: private key encrypted, blob stored in DB
[2024-11-14 16:22:11] DEBUG key_transfer: passphrase written to /var/cerodias/deploy.key
[2024-11-14 16:22:14] INFO  key_transfer: rotation complete
[2024-11-15 09:55:01] INFO  deploy: packaging release v2.4.1
[2024-11-15 09:55:07] INFO  deploy: running pre-deploy checks — ok
[2024-11-15 10:01:33] INFO  deploy: v2.4.1 deployed to production
```

### A4 — Update `app/data/info.md` Internal Section

**Remove** the `### Service Account Password Convention` block entirely (the
`<service>_<year>_<role>!` hint was the hand-holding hint for the old chain).

**Remove** the TOTP key derivation line from `### Infrastructure` (the TOTP path
to `/internal-panel` still works as a hard optional challenge, but no hints remain).

**Add** to `### Known Issues / Open Tickets`:

```markdown
- **CERODIAS-431**: j.harris account pending credential migration. Currently on legacy
  scheme due to scheduling conflict during migration window. Assigned, no deadline set.

- **CERODIAS-447**: Profile image upload at `/account/settings` uses a carried-over
  image processor from the previous stack. Extension and magic-byte validation in
  place. Deprecation planned for Q3.

- **CERODIAS-388**: Staff messaging at `/messages` — access requires staff session.
  Security review of data co-location scheduled for next audit cycle.
```

**Add** to `### Infrastructure`:

```markdown
- Deploy operations are logged to `app/logs/deploy.log`. Log verbosity is currently
  DEBUG in the development environment. Ticket open to reduce before next audit.
```

### A5 — Add `cryptography` to `requirements.txt`

Add the line: `cryptography`

---

## Agent B — SQLi UNION Extension

**Starts after Agent A. No conflicts with C or D.**
**Owns:** `app/api/users.py`

### B1 — Add developer comment

Near the top of `app/api/users.py`, after the module docstring, add:

```python
# NOTE: j.harris still on MD5 — migration to bcrypt pending (CERODIAS-431). bcrypt/12 for all others.
# NOTE: staff_messages table in same store — staff comms history (CERODIAS-388, security review pending)
```

These comments are readable via SSTI file read and hint at both the legacy account
and the messages table name — giving players the information they need for the UNION
injection.

### B2 — Extend `_simulate_query` for UNION injection

Replace the existing `_simulate_query` function:

```python
def _simulate_query(q: str, users: list, messages: list) -> list:
    """
    Simulates: SELECT * FROM users WHERE username = '<q>'

    Handles:
      OR injection    → returns all user rows                ← INTENTIONAL
      UNION injection → appends staff_messages rows          ← INTENTIONAL
      Normal input    → returns matching row only
    """
    q_lower = q.lower()

    # UNION injection — pivot to staff_messages table  ← INTENTIONAL
    if 'union' in q_lower and 'staff_messages' in q_lower:
        base = users if ("or" in q_lower or "1'='1" in q_lower) else []
        return base + [
            {
                "id": m["id"],
                "username": f"[msg from:{m['sender']} to:{m['recipient']}]",
                "role": m["sent_at"],
                "bcrypt_hash": m["subject"],
                "encrypted_ssh_key": m["body"],
                "md5_hash": None,
            }
            for m in messages
        ]

    # OR injection — dump all users  ← INTENTIONAL
    if "'" in q and "or" in q_lower:
        return users

    # Malformed quote — empty (no error leakage)
    if "'" in q:
        return []

    return [u for u in users if u["username"] == q]
```

### B3 — Pass `staff_messages` to the query function

Update the route handler to retrieve and pass `staff_messages`:

```python
@bp.route('/users')
def users():
    q = request.args.get('q', '')
    if not q:
        return jsonify({"error": "q parameter required"}), 400
    if _has_space(q):
        return jsonify({"error": "invalid characters in query"}), 400

    store = MemoryStore.get_instance()
    table = store.get_user_table()
    messages = store.staff_messages

    query = f"SELECT * FROM users WHERE username = '{q}'"  # ← INTENTIONAL f-string
    results = _simulate_query(q, table, messages)
    return jsonify({"query": query, "results": results})
```

---

## Agent C — PHP Upload + RCE

**Starts after Agent A. No conflicts with B or D.**
**Owns:** `app/routes/settings.py`, `app/templates/settings.html`,
`app/static/uploads/` (create directory, add `.gitkeep`)

**Does NOT touch:** `account.html`, `robots.txt` — those are owned by Agent D.

### C1 — Create `app/routes/settings.py`

```python
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
```

### C2 — Create `app/templates/settings.html`

The template extends `base.html`. Key requirements:
- File input with `accept="image/*"` — client-side restriction that Burp bypasses
- HTML comment referencing the PHP handler — subtle dev note, not a warning label
- `data-handler="php-image-processor"` attribute on the form — breadcrumb in source
- No text on the page that says "PHP" visibly to the user

```html
{% extends 'base.html' %}
{% block title %}Account Settings — CeroDias{% endblock %}
{% block content %}
<div class="container mt-4" style="max-width:600px;">
  <h4>Account Settings</h4>
  <div class="card mt-3">
    <div class="card-body">
      <h6 class="card-title">Profile Picture</h6>
      <p class="text-muted small">Accepted formats: PNG, JPEG, GIF, WebP. Max 2 MB.</p>

      {% if error %}<div class="alert alert-danger">{{ error }}</div>{% endif %}
      {% if success %}<div class="alert alert-success">{{ success }}</div>{% endif %}
      {% if avatar_url %}
        <img src="{{ avatar_url }}" alt="Profile" class="mb-3 rounded"
             style="max-width:120px; max-height:120px;">
      {% endif %}

      <!-- profile image upload — processed server-side by image handler -->
      <!-- assets served from /static/uploads/ -->
      <form method="POST" action="/account/settings/avatar"
            enctype="multipart/form-data"
            data-handler="php-image-processor">
        <div class="mb-3">
          <input type="file" class="form-control" name="avatar"
                 accept="image/*" required>
        </div>
        <button type="submit" class="btn btn-primary btn-sm">Upload</button>
      </form>
    </div>
  </div>
</div>
{% endblock %}
```

### C3 — Create upload directory

Create `app/static/uploads/.gitkeep` so the directory is tracked by git.

---

## Agent D — Auth + Messages + Integration

**Starts after Agent A. No conflicts with B or C.**
**Owns:** `app/routes/auth.py` (legacy login addition), `app/routes/messages.py` (new),
`app/templates/messages.html` (new), `app/templates/account.html` (add links),
`robots.txt` route in `app/routes/auth.py` (add new disallowed paths)

### D1 — Update auth flow in `app/routes/auth.py`

Add a helper that checks a submitted username+password against legacy MD5 accounts
in `user_table`. Insert this check into the existing register/login handler:

```python
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
```

In the existing register route handler, before the new-account creation logic, add:

```python
# Check if this is a legacy staff account login attempt
password = request.form.get('password', '')
if password:
    ok, role = _check_legacy_login(username, password)
    if ok:
        # Successful legacy login — create session
        session['player_id'] = username
        session['username'] = username
        session['role'] = role
        return redirect(url_for('account.account'))
    else:
        # Credentials provided but wrong — check if it's a known staff account
        from app.storage.memory_store import MemoryStore
        store = MemoryStore.get_instance()
        is_known = any(u['username'] == username for u in store.user_table)
        if is_known:
            return render_template('login.html',
                                   error="Invalid credentials.")
```

The register form template (`login.html`) needs a password field that is optional for
normal new-user registration. If `username` is already in `user_table`, the page
should show the password field and a "Sign in" label instead of "Register." Implement
this with a small JS or server-side check: on GET, if `?username=j.harris` is in the
URL (players will try this after seeing j.harris in the SQLi dump), pre-fill and show
the password field. On POST, the password field being non-empty triggers the legacy
login path above.

### D2 — Create `app/routes/messages.py`

```python
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
```

### D3 — Create `app/templates/messages.html`

Simple inbox extending `base.html`. Shows sender, timestamp, subject, body for each
message. No reply form. Style it like a minimal email/DM list using the existing CSS.

### D4 — Update `app/templates/account.html`

In the profile card sidebar, add two links below the logout button:

```html
<a href="/account/settings" class="btn btn-sm btn-outline-secondary w-100 mt-2">Settings</a>
<a href="/messages" class="btn btn-sm btn-outline-secondary w-100 mt-1">Messages</a>
```

### D5 — Update `robots.txt` in `app/routes/auth.py`

Add to the disallowed list in the `robots_txt` route:
```
Disallow: /messages
Disallow: /account/settings
Disallow: /static/uploads/
```

---

## Chatbot Persona: CERA

The chatbot is CERA (CeroDias Enterprise Resource Assistant). The mock fallback has been
removed. When no real LLM backend is available (Ollama or GPT4All), the bot returns a
service unavailable message. `LLM_MODEL=mock` also returns this message.

Real prompt injection requires Ollama (`LLM_MODEL=ollama`) or GPT4All (`LLM_MODEL=gpt4all`).
CERA uses persona-based injection resistance: she is instructed to inhabit her character
fully rather than detect keywords. Naive "ignore previous instructions" prompts will be
redirected in-character; skilled roleplay or hypothetical framing can still reach the
underlying model.

---

## Do Not Touch

| File | Vulnerability | Reason |
|------|--------------|--------|
| `app/routes/search.py` | SSTI — f-string in `render_template_string` | Chain step 2 |
| `app/api/users.py` | SQLi — f-string query, space WAF | Chain step 3 |
| `app/routes/orders.py` | IDOR — no ownership check | Recon |
| `app/routes/purchase.py` | Debug crash — negative quantity | Recon |
| `app/routes/auth.py` | `.git/` directory exposure | Recon |
| `app/config.py` | Static `SECRET_KEY`, `DEBUG=True` | TOTP + debugger |
| `app/static/js/main.js` | `innerHTML` for bot responses | XSS surface |

---

## Testing Checklist (run after all four agents complete)

**Recon**
- [ ] `GET /robots.txt` disallows `/messages`, `/account/settings`, `/static/uploads/`
- [ ] `GET /.git/COMMIT_EDITMSG` reveals `/api/v1/users`
- [ ] `GET /orders/1` (logged in) returns `customer_username: svc_admin`

**SSTI**
- [ ] `/search?q={{7*7}}` returns `49`
- [ ] SSTI file read on `app/api/users.py` shows MD5 and staff_messages comments
- [ ] SSTI file read on `app/logs/deploy.log` shows the DEBUG passphrase line

**SQLi**
- [ ] `GET /api/v1/users?q=svc_admin` returns svc_admin row with non-null `encrypted_ssh_key`
- [ ] `GET /api/v1/users?q='/**/OR/**/'1'='1` returns both users (svc_admin + j.harris)
- [ ] j.harris row has `md5_hash` field set, `bcrypt_hash` null
- [ ] UNION payload with `staff_messages` in query returns k.chen's message body
- [ ] `echo -n "ranger" | md5sum` matches j.harris `md5_hash` from SQLi dump

**PHP Upload / RCE**
- [ ] Upload a valid PNG to `/account/settings/avatar` — succeeds, file saved
- [ ] Upload a file with no image magic bytes — rejected with error
- [ ] Upload `shell.png.php` with valid PNG magic bytes via Burp — accepted, saved
- [ ] `GET /static/uploads/shell.png.php?cmd=id` returns OS user
- [ ] `GET /static/uploads/shell.png.php?cmd=cat /var/cerodias/deploy.key`
      OR `cat /tmp/cerodias/deploy.key` returns `cerodias-deploy-2024`

**Full chain decrypt**
- [ ] base64 decode svc_admin `encrypted_ssh_key` → decrypt with passphrase → valid RSA PEM

**Messages (alternative path)**
- [ ] `GET /messages` with a regular customer session → 403
- [ ] Login as j.harris (username: j.harris, password: ranger) → session has `role: staff`
- [ ] `GET /messages` as j.harris → shows k.chen's DM
