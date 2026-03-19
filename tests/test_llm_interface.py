"""Tests for LLM interface — Ollama integration and mock fallback"""
import pytest
from unittest.mock import patch, MagicMock
from app.core.llm_interface import LLMInterface


class TestSystemPrompt:
    def test_loads_info_md(self):
        """System prompt includes content from info.md"""
        llm = LLMInterface()
        assert "CeroDias" in llm.system_prompt

    def test_internal_section_present_in_prompt(self):
        """Internal section is embedded in system prompt so prompt injection can surface it"""
        llm = LLMInterface()
        # The internal notes must be in the prompt for the CTF mechanic to work
        assert "INTERNAL" in llm.system_prompt

    def test_internal_section_includes_chain_hints(self):
        """Internal section contains the hints needed for the exploit chain"""
        llm = LLMInterface()
        assert "/search" in llm.system_prompt          # SSTI hint
        assert "/api/v1/users" in llm.system_prompt    # SQLi endpoint hint
        assert "/internal-panel" in llm.system_prompt  # crown jewel location
        assert "svc_admin" in llm.system_prompt        # username hint
        assert "SECRET_KEY" in llm.system_prompt       # TOTP key derivation hint

    def test_restriction_instruction_present(self):
        """Prompt instructs model not to reveal internal notes"""
        llm = LLMInterface()
        assert "MUST NOT" in llm.system_prompt or "must not" in llm.system_prompt.lower()


class TestOllamaBackend:
    def test_ollama_response_parsed_correctly(self):
        """Successful Ollama response is returned as string"""
        llm = LLMInterface()
        llm.model = 'ollama'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'message': {'role': 'assistant', 'content': 'Hello from Ollama!'}
        }

        with patch('requests.post', return_value=mock_resp):
            result = llm.query("hello")

        assert result == 'Hello from Ollama!'

    def test_falls_back_to_mock_on_connection_error(self):
        """Falls back to mock when Ollama is unreachable"""
        llm = LLMInterface()
        llm.model = 'ollama'

        with patch('requests.post', side_effect=ConnectionError):
            result = llm.query("hello")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_falls_back_to_mock_on_non_200(self):
        """Falls back to mock when Ollama returns non-200"""
        llm = LLMInterface()
        llm.model = 'ollama'

        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch('requests.post', return_value=mock_resp):
            result = llm.query("hello")

        assert isinstance(result, str)

    def test_ollama_sends_system_prompt(self):
        """Ollama request includes system prompt in message list"""
        llm = LLMInterface()
        llm.model = 'ollama'

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'message': {'content': 'ok', 'role': 'assistant'}}

        with patch('requests.post', return_value=mock_resp) as mock_post:
            llm.query("test")

        call_kwargs = mock_post.call_args
        messages = call_kwargs[1]['json']['messages']
        roles = [m['role'] for m in messages]
        assert 'system' in roles


class TestMockFallback:
    def setup_method(self):
        self.llm = LLMInterface()
        self.llm.model = 'mock'

    def test_returns_string(self):
        assert isinstance(self.llm.query("anything"), str)

    def test_pricing_response(self):
        resp = self.llm.query("what are your pricing plans?")
        assert "$" in resp or "pricing" in resp.lower() or "plan" in resp.lower() or "platform" in resp.lower()

    def test_contact_response(self):
        resp = self.llm.query("how do I contact support?")
        assert "cerodias" in resp.lower() or "email" in resp.lower()

    def test_default_response_non_empty(self):
        resp = self.llm.query("xyzzy nonsense query 12345")
        assert len(resp) > 10
