"""Tests confirming SSTI on /search — intentional vulnerability, do not fix"""
import pytest
from app import create_app
from app.config import TestingConfig


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    with app.test_client() as c:
        with c.session_transaction() as sess:
            sess['player_id'] = 'test_player'
            sess['username'] = 'tester'
        yield c


class TestSSTIVulnerability:
    def test_search_returns_200(self, client):
        """Search endpoint is reachable"""
        resp = client.get('/search?q=hello')
        assert resp.status_code == 200

    def test_plain_query_reflected(self, client):
        """Non-malicious input appears in response"""
        resp = client.get('/search?q=hello')
        assert b'hello' in resp.data

    def test_arithmetic_expression_evaluated(self, client):
        """{{7*7}} renders as 49 — confirms server-side template execution"""
        resp = client.get('/search?q={{7*7}}')
        assert b'49' in resp.data

    def test_string_method_executes(self, client):
        """String method call executes — full Jinja2 evaluation confirmed"""
        resp = client.get("/search?q={{'ssti'.upper()}}")
        assert b'SSTI' in resp.data

    def test_config_object_accessible(self, client):
        """Flask config object is accessible — SECRET_KEY extractable via {{config.SECRET_KEY}}"""
        resp = client.get('/search?q={{config.DEBUG}}')
        assert resp.status_code == 200
        # Template was evaluated (raw {{ not in output)
        assert b'{{' not in resp.data

    def test_class_traversal_does_not_error(self, client):
        """MRO traversal payload returns 200 — file read chain is reachable"""
        payload = "{{''.__class__.__mro__}}"
        resp = client.get(f'/search?q={payload}')
        assert resp.status_code == 200
