"""
Shared pytest fixtures for all CeroDias chain tests.

Three client fixtures are provided:
  client         — unauthenticated (no session)
  authed_client  — logged-in as a regular player ("testplayer")
  harris_client  — logged-in as j.harris (staff role, via legacy MD5 login)

Import any of these in your test file with a standard pytest fixture argument.
"""
import pytest
from app import create_app
from app.config import TestingConfig
from app.storage.memory_store import MemoryStore

# ---------------------------------------------------------------------------
# Tunable constants — change here, not inside test bodies
# ---------------------------------------------------------------------------
REGULAR_USER = "testplayer"
HARRIS_USER = "j.harris"
HARRIS_PASSWORD = "ranger"


@pytest.fixture(scope="session")
def app():
    """Create the Flask application once per test session."""
    application = create_app(TestingConfig)
    return application


@pytest.fixture
def client(app):
    """Unauthenticated test client."""
    with app.test_client() as c:
        yield c


@pytest.fixture
def authed_client(app):
    """Authenticated client — regular player session (no staff role)."""
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess["player_id"] = REGULAR_USER
            sess["username"] = REGULAR_USER
        yield c


@pytest.fixture
def harris_client(app):
    """
    Authenticated client for j.harris.

    Uses the live /register POST endpoint with the correct MD5 password so the
    session is established exactly as a real attacker would do it — no manual
    session patching.
    """
    with app.test_client() as c:
        resp = c.post(
            "/register",
            data={"username": HARRIS_USER, "password": HARRIS_PASSWORD},
            follow_redirects=False,
        )
        # Successful legacy login redirects to /account
        assert resp.status_code in (301, 302), (
            f"j.harris login did not redirect (got {resp.status_code}). "
            "Check _check_legacy_login in auth.py and the MD5 hash in memory_store.py."
        )
        yield c
