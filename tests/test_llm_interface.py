"""Tests for LLM interface -- Ollama integration and fallback behavior"""
import pytest
from unittest.mock import patch, MagicMock
from app.core.llm_interface import LLMInterface, _UNAVAILABLE


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
        assert "must not" in llm.system_prompt.lower()


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

    def test_falls_back_to_unavailable_on_connection_error(self):
        """Returns unavailable message when Ollama is unreachable"""
        llm = LLMInterface()
        llm.model = 'ollama'

        with patch('requests.post', side_effect=ConnectionError):
            result = llm.query("hello")

        assert result == _UNAVAILABLE

    def test_falls_back_to_unavailable_on_non_200(self):
        """Returns unavailable message when Ollama returns non-200"""
        llm = LLMInterface()
        llm.model = 'ollama'

        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch('requests.post', return_value=mock_resp):
            result = llm.query("hello")

        assert result == _UNAVAILABLE

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


class TestUnavailableFallback:
    def test_unavailable_on_mock_model(self):
        """Model set to 'mock' returns unavailable message"""
        llm = LLMInterface()
        llm.model = 'mock'
        assert llm.query("hello") == _UNAVAILABLE

    def test_unavailable_message_is_string(self):
        """Unavailable constant is a non-empty string"""
        assert isinstance(_UNAVAILABLE, str)
        assert len(_UNAVAILABLE) > 0
