import sys
from flask import Flask
from app.config import DevelopmentConfig


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
            format=serialization.PrivateFormat.TraditionalOpenSSL,
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


def _check_llm(app):
    """Check Ollama is reachable. Warn clearly if not."""
    from app.core.llm_interface import is_configured, OLLAMA_URL, OLLAMA_MODEL
    app.config['CERA_ENABLED'] = is_configured()
    if app.config['CERA_ENABLED']:
        print(f"  CERA enabled (Ollama at {OLLAMA_URL}, model: {OLLAMA_MODEL})", file=sys.stderr)
    else:
        print(
            "\n"
            "  CERA chatbot is disabled -- Ollama is not running.\n"
            "\n"
            "  To enable it:\n"
            f"    1. Install Ollama:      https://ollama.com\n"
            f"    2. Pull a model:        ollama pull {OLLAMA_MODEL}\n"
            f"    3. Start Ollama:        ollama serve\n"
            f"    4. Restart this server.\n"
            "\n"
            "  The rest of the site works normally without it.\n",
            file=sys.stderr,
        )


def create_app(config_class=DevelopmentConfig):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # ── Page / view routes ──────────────────────────────────────────
    from app.routes import auth, challenges, submit, dashboard, chatbot, admin, search
    from app.routes import account, orders, purchase

    app.register_blueprint(auth.bp)
    app.register_blueprint(challenges.bp)
    app.register_blueprint(submit.bp)
    app.register_blueprint(dashboard.bp)
    app.register_blueprint(chatbot.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(search.bp)
    app.register_blueprint(account.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(purchase.bp)

    from app.routes import settings, messages
    app.register_blueprint(settings.bp)
    app.register_blueprint(messages.bp)

    # ── JSON API routes  (/api/v1/) ─────────────────────────────────
    from app.api import users as api_users

    app.register_blueprint(api_users.bp)

    # ── Internal / hidden routes  (/internal-panel) ─────────────────
    from app.internal import panel

    app.register_blueprint(panel.bp)

    from app.storage.memory_store import MemoryStore
    _seed_ssh_key(MemoryStore.get_instance())

    _check_llm(app)

    @app.context_processor
    def inject_cera_enabled():
        return {'cera_enabled': app.config.get('CERA_ENABLED', False)}

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('error.html', error_code=404, error='Page not found.'), 404

    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template('error.html', error_code=403, error='Access denied.'), 403

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template('error.html', error_code=500, error=str(e)), 500

    return app
