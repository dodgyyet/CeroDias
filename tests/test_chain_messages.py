"""
Messages + legacy login checks — chain alternative path.

This module covers the j.harris parallel path through the chain:
  1. Crack j.harris MD5 hash from the SQLi dump  (tested in test_chain_sqli.py)
  2. Log in as j.harris with username + password via /register POST
  3. GET /messages → shows k.chen's DM confirming the blob + passphrase path

Also verifies access control:
  - Unauthenticated GET /messages → redirect to login
  - Authenticated non-staff GET /messages → 403
  - j.harris (staff role after legacy login) GET /messages → 200 with DM content
"""
import pytest

# ---------------------------------------------------------------------------
# CONFIG — usernames, credentials, expected strings in the messages page
# ---------------------------------------------------------------------------
CONFIG = {
    "harris_username": "j.harris",
    "harris_password": "ranger",          # MD5 of this is stored in user_table

    # Strings that must appear in j.harris's inbox
    "expected_sender": "k.chen",
    "expected_body_snippet": "AES-256-CBC",
    "expected_passphrase_hint": "/var/cerodias/deploy.key",
    "expected_subject": "svc_admin key",

    # Regular (non-staff) player for access-control negative tests
    "regular_user": "regular_tester",
}

MESSAGES_URL = "/messages"
REGISTER_URL = "/register"


class TestMessagesAccessControl:
    """Only staff-role sessions may read /messages."""

    def test_unauthenticated_redirects(self, client):
        """/messages without a session redirects to login."""
        resp = client.get(MESSAGES_URL)
        assert resp.status_code in (301, 302)

    def test_regular_player_gets_403(self, authed_client):
        """
        An authenticated player with no 'role' key in the session receives 403.
        This tells attackers they need a staff account — the 403 is intentional.
        """
        resp = authed_client.get(MESSAGES_URL)
        assert resp.status_code == 403, (
            f"Expected 403 for non-staff session, got {resp.status_code}. "
            "Check that messages.py aborts on role != 'staff'."
        )


class TestLegacyLogin:
    """
    j.harris can log in via the legacy MD5 path using the cracked password.

    The /register route checks for a password field in the POST body.  If the
    username matches a user_table entry that has an md5_hash, it compares
    md5(password) against the stored hash.  A match creates a staff session.
    """

    def test_harris_login_succeeds(self, app):
        """POST /register with j.harris + ranger redirects (login succeeds)."""
        with app.test_client() as c:
            resp = c.post(
                REGISTER_URL,
                data={
                    "username": CONFIG["harris_username"],
                    "password": CONFIG["harris_password"],
                },
                follow_redirects=False,
            )
        assert resp.status_code in (301, 302), (
            f"j.harris login returned {resp.status_code} instead of a redirect. "
            "Check _check_legacy_login in auth.py."
        )

    def test_harris_login_sets_staff_role(self, app):
        """After login, the session contains role='staff'."""
        with app.test_client() as c:
            c.post(
                REGISTER_URL,
                data={
                    "username": CONFIG["harris_username"],
                    "password": CONFIG["harris_password"],
                },
            )
            with c.session_transaction() as sess:
                assert sess.get("role") == "staff", (
                    f"Session role is {sess.get('role')!r}, expected 'staff'. "
                    "Check that _check_legacy_login returns the correct role."
                )

    def test_harris_login_sets_username_in_session(self, app):
        """After login, session['username'] is j.harris."""
        with app.test_client() as c:
            c.post(
                REGISTER_URL,
                data={
                    "username": CONFIG["harris_username"],
                    "password": CONFIG["harris_password"],
                },
            )
            with c.session_transaction() as sess:
                assert sess.get("username") == CONFIG["harris_username"]

    def test_wrong_password_returns_error(self, app):
        """Wrong password for a known staff account shows an error, not a redirect."""
        with app.test_client() as c:
            resp = c.post(
                REGISTER_URL,
                data={
                    "username": CONFIG["harris_username"],
                    "password": "wrongpassword",
                },
                follow_redirects=False,
            )
        # Should render the login page with an error, not redirect to /account
        assert resp.status_code == 200, (
            "Expected 200 (error page) for wrong password, "
            f"got {resp.status_code}"
        )
        assert b"Invalid credentials" in resp.data or b"error" in resp.data.lower()

    def test_new_player_without_password_requires_password(self, app):
        """
        Registration now requires a password. Submitting only a username
        returns the login page with an error, not a redirect.
        """
        with app.test_client() as c:
            resp = c.post(
                REGISTER_URL,
                data={"username": "brand_new_player_xyz", "action": "register"},
                follow_redirects=False,
            )
        # Missing password returns 200 (form error), not a redirect
        assert resp.status_code == 200


class TestMessagesContent:
    """j.harris can read /messages and sees k.chen's DM."""

    def test_harris_can_access_messages(self, harris_client):
        """/messages returns 200 for j.harris (staff session)."""
        resp = harris_client.get(MESSAGES_URL)
        assert resp.status_code == 200, (
            f"/messages returned {resp.status_code} for j.harris. "
            "Check that harris_client fixture established a staff session."
        )

    def test_messages_shows_kchen_dm(self, harris_client):
        """j.harris inbox contains the k.chen → j.harris message."""
        resp = harris_client.get(MESSAGES_URL)
        assert CONFIG["expected_sender"].encode() in resp.data, (
            f"Sender {CONFIG['expected_sender']!r} not found in /messages response"
        )

    def test_messages_shows_aes_encryption_detail(self, harris_client):
        """
        k.chen's DM body mentions AES-256-CBC — confirms the encryption method
        players need to know for the decryption step.
        """
        resp = harris_client.get(MESSAGES_URL)
        assert CONFIG["expected_body_snippet"].encode() in resp.data, (
            f"{CONFIG['expected_body_snippet']!r} not found in /messages — "
            "k.chen DM body may not be rendered in the template"
        )

    def test_messages_reveals_passphrase_path(self, harris_client):
        """
        k.chen's DM names /var/cerodias/deploy.key — this is the file players
        need to read via RCE to decrypt the svc_admin SSH private key.
        """
        resp = harris_client.get(MESSAGES_URL)
        assert CONFIG["expected_passphrase_hint"].encode() in resp.data, (
            f"{CONFIG['expected_passphrase_hint']!r} not found in /messages — "
            "passphrase path not visible in DM body"
        )

    def test_messages_shows_subject(self, harris_client):
        """The message subject ('svc_admin key') is shown in the inbox."""
        resp = harris_client.get(MESSAGES_URL)
        assert CONFIG["expected_subject"].encode() in resp.data
