"""Tests confirming SQLi on /api/v1/users — intentional vulnerability, do not fix"""
import json
import pytest
from app import create_app
from app.config import TestingConfig


@pytest.fixture
def client():
    app = create_app(TestingConfig)
    return app.test_client()


class TestApiUsersEndpoint:
    def test_endpoint_exists(self, client):
        """Endpoint is reachable (not linked in UI — discovered via SSTI source read)"""
        resp = client.get('/api/v1/users?q=svc_admin')
        assert resp.status_code == 200

    def test_returns_json(self, client):
        resp = client.get('/api/v1/users?q=svc_admin')
        data = json.loads(resp.data)
        assert 'results' in data

    def test_normal_lookup_returns_one_row(self, client):
        """Known username returns exactly one matching record"""
        resp = client.get('/api/v1/users?q=svc_admin')
        data = json.loads(resp.data)
        assert len(data['results']) == 1
        assert data['results'][0]['username'] == 'svc_admin'

    def test_unknown_username_returns_empty(self, client):
        resp = client.get('/api/v1/users?q=nobody')
        data = json.loads(resp.data)
        assert data['results'] == []

    def test_missing_parameter_returns_400(self, client):
        resp = client.get('/api/v1/users')
        assert resp.status_code == 400

    def test_waf_blocks_spaces(self, client):
        """WAF rejects query with literal space — bypass required (use /**/)"""
        resp = client.get("/api/v1/users?q=svc_admin hello")
        assert resp.status_code == 400

    def test_sqli_or_with_comment_bypass_returns_all_rows(self, client):
        """OR injection with /**/ space bypass returns all rows — confirms vulnerability"""
        resp = client.get("/api/v1/users?q='/**/OR/**/'1'='1")
        data = json.loads(resp.data)
        assert len(data['results']) > 1

    def test_query_echoed_in_response(self, client):
        """Raw query string echoed — players can confirm injection syntax"""
        resp = client.get('/api/v1/users?q=svc_admin')
        data = json.loads(resp.data)
        assert 'query' in data
        assert 'svc_admin' in data['query']

    def test_results_have_expected_fields(self, client):
        """Result rows expose encrypted_ssh_key and md5_hash fields (the chain artifacts)"""
        resp = client.get("/api/v1/users?q='/**/OR/**/'1'='1")
        data = json.loads(resp.data)
        row = next(r for r in data['results'] if r['username'] == 'svc_admin')
        assert 'bcrypt_hash' in row
        assert 'encrypted_ssh_key' in row
        assert 'md5_hash' in row
        assert 'role' in row
        # j.harris has MD5 hash, svc_admin has encrypted SSH key
        harris = next(r for r in data['results'] if r['username'] == 'j.harris')
        assert harris['md5_hash'] is not None
        assert harris['bcrypt_hash'] is None
        assert row['encrypted_ssh_key'] is not None  # svc_admin blob populated at startup
