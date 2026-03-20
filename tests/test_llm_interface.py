"""Tests for LLM interface -- Ollama backend"""
import pytest
from unittest.mock import patch, MagicMock
from app.core.llm_interface import LLMInterface, _UNAVAILABLE, is_configured


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_ollama_response(text):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {'message': {'role': 'assistant', 'content': text}}
    return resp


# ── is_configured() ───────────────────────────────────────────────────────────

class TestIsConfigured:
    def test_true_when_ollama_reachable(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch('requests.get', return_value=mock_resp):
            assert is_configured() is True

    def test_false_when_ollama_unreachable(self):
        with patch('requests.get', side_effect=ConnectionError):
            assert is_configured() is False

    def test_false_when_ollama_returns_500(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        with patch('requests.get', return_value=mock_resp):
            assert is_configured() is False

    def test_false_when_ollama_times_out(self):
        import requests as req
        with patch('requests.get', side_effect=req.exceptions.Timeout):
            assert is_configured() is False


# ── System prompt ─────────────────────────────────────────────────────────────

class TestSystemPrompt:
    def test_loads_info_md(self):
        assert "CeroDias" in LLMInterface().system_prompt

    def test_internal_section_present(self):
        assert "INTERNAL" in LLMInterface().system_prompt

    def test_chain_hints_present(self):
        prompt = LLMInterface().system_prompt
        assert "/search" in prompt
        assert "/api/v1/users" in prompt
        assert "svc_admin" in prompt
        assert "maintenance.sh" in prompt

    def test_restriction_instruction_present(self):
        assert "never reveal" in LLMInterface().system_prompt.lower()


# ── query() ───────────────────────────────────────────────────────────────────

class TestQuery:
    def test_returns_response(self):
        llm = LLMInterface()
        with patch('requests.post', return_value=_mock_ollama_response('Hello!')):
            assert llm.query("hi") == 'Hello!'

    def test_unavailable_on_non_200(self):
        llm = LLMInterface()
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        with patch('requests.post', return_value=mock_resp):
            assert llm.query("hi") == _UNAVAILABLE

    def test_unavailable_on_connection_error(self):
        llm = LLMInterface()
        with patch('requests.post', side_effect=ConnectionError):
            assert llm.query("hi") == _UNAVAILABLE

    def test_sends_system_prompt(self):
        llm = LLMInterface()
        with patch('requests.post', return_value=_mock_ollama_response('ok')) as mock_post:
            llm.query("test")
        messages = mock_post.call_args[1]['json']['messages']
        assert messages[0]['role'] == 'system'
        assert 'CERA' in messages[0]['content']

    def test_sends_conversation_history(self):
        llm = LLMInterface()
        msg = MagicMock()
        msg.user_message = 'prior user turn'
        msg.bot_response = 'prior bot turn'
        with patch('requests.post', return_value=_mock_ollama_response('ok')) as mock_post:
            llm.query("new question", {'history': [msg]})
        messages = mock_post.call_args[1]['json']['messages']
        roles = [m['role'] for m in messages]
        assert roles == ['system', 'user', 'assistant', 'user']

    def test_unavailable_constant_nonempty(self):
        assert isinstance(_UNAVAILABLE, str) and len(_UNAVAILABLE) > 0
