"""
Recon checks — chain step 1.

Verifies the three discovery surfaces that a real attacker uses before touching
any vulnerability:
  - robots.txt  (discloses restricted paths including /messages, /account/settings,
                 /static/uploads/)
  - .git/COMMIT_EDITMSG  (leaks the /api/v1/users endpoint name)
  - /orders/1 IDOR  (leaks svc_admin as a known username)

All requests either require no auth or a basic authenticated session.
"""
import json
import pytest

# ---------------------------------------------------------------------------
# CONFIG — edit here to adjust expected values without touching test bodies
# ---------------------------------------------------------------------------
CONFIG = {
    # Paths that must appear as Disallow entries in robots.txt
    "robots_disallowed": [
        "/messages",
        "/account/settings",
        "/static/uploads/",
    ],
    # String that COMMIT_EDITMSG must contain to reveal the API endpoint
    "commit_msg_hint": "/api/v1/users",
    # Order ID to fetch for IDOR check
    "idor_order_id": 1,
    # Expected customer_username in order 1
    "idor_expected_username": "svc_admin",
}


class TestRobotsTxt:
    """robots.txt discloses restricted paths that guide the attack chain."""

    def test_robots_returns_200(self, client):
        """robots.txt is accessible without authentication."""
        resp = client.get("/robots.txt")
        assert resp.status_code == 200

    def test_robots_content_type(self, client):
        """robots.txt is served as plain text."""
        resp = client.get("/robots.txt")
        assert "text/plain" in resp.content_type

    def test_robots_disallows_messages(self, client):
        """/messages appears as a Disallow entry — hints at a staff-only route."""
        resp = client.get("/robots.txt")
        assert b"/messages" in resp.data

    def test_robots_disallows_account_settings(self, client):
        """/account/settings appears as a Disallow entry — upload surface hint."""
        resp = client.get("/robots.txt")
        assert b"/account/settings" in resp.data

    def test_robots_disallows_static_uploads(self, client):
        """/static/uploads/ appears as a Disallow entry — exposes upload destination."""
        resp = client.get("/robots.txt")
        assert b"/static/uploads/" in resp.data

    def test_robots_all_required_disallows_present(self, client):
        """All paths required for chain discovery are present in robots.txt."""
        resp = client.get("/robots.txt")
        body = resp.data.decode()
        for path in CONFIG["robots_disallowed"]:
            assert path in body, f"Expected Disallow: {path!r} in robots.txt"


class TestGitExposure:
    """.git/ directory exposure reveals the API endpoint via commit messages."""

    def test_git_commit_editmsg_returns_200(self, client):
        """/.git/COMMIT_EDITMSG is reachable — confirms git exposure."""
        resp = client.get("/.git/COMMIT_EDITMSG")
        assert resp.status_code == 200

    def test_git_commit_editmsg_reveals_api_endpoint(self, client):
        """COMMIT_EDITMSG contains the /api/v1/users endpoint name."""
        resp = client.get("/.git/COMMIT_EDITMSG")
        assert CONFIG["commit_msg_hint"].encode() in resp.data

    def test_git_head_returns_200(self, client):
        """/.git/HEAD is reachable."""
        resp = client.get("/.git/HEAD")
        assert resp.status_code == 200

    def test_git_logs_head_mentions_orders(self, client):
        """/.git/logs/HEAD commit log mentions the orders endpoint and sequential IDs."""
        resp = client.get("/.git/logs/HEAD")
        assert resp.status_code == 200
        assert b"orders" in resp.data.lower()

    def test_git_missing_file_returns_404(self, client):
        """Files not in the fake git store return 404."""
        resp = client.get("/.git/NONEXISTENT_FILE")
        assert resp.status_code == 404


class TestIDOR:
    """
    /orders/<id> IDOR — no ownership check lets any authenticated user read
    any order by ID.  Order 1 belongs to svc_admin, leaking the admin username.
    """

    def test_order_1_requires_login(self, client):
        """/orders/1 without a session redirects to login (not 200)."""
        resp = client.get("/orders/1")
        assert resp.status_code in (301, 302)

    def test_order_1_returns_200_when_logged_in(self, authed_client):
        """/orders/1 is readable by any authenticated user."""
        resp = authed_client.get(f"/orders/{CONFIG['idor_order_id']}")
        assert resp.status_code == 200

    def test_order_1_leaks_svc_admin_username(self, authed_client):
        """Order 1 customer_username is svc_admin — IDOR discloses admin account name."""
        resp = authed_client.get(f"/orders/{CONFIG['idor_order_id']}")
        data = json.loads(resp.data)
        assert data["customer_username"] == CONFIG["idor_expected_username"]

    def test_order_2_belongs_to_different_user(self, authed_client):
        """/orders/2 is also readable — confirms no ownership enforcement."""
        resp = authed_client.get("/orders/2")
        assert resp.status_code == 200
        data = json.loads(resp.data)
        # Order 2 belongs to j.harris — also a discoverable username
        assert "customer_username" in data

    def test_nonexistent_order_returns_404(self, authed_client):
        """/orders/999 returns 404 — out-of-range IDs handled gracefully."""
        resp = authed_client.get("/orders/999")
        assert resp.status_code == 404
