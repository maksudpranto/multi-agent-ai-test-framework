import pytest

from app.config import Settings
from app.llm.gemini_provider import GeminiProvider
from app.llm.mock_provider import MockProvider
from app.llm.ollama_provider import OllamaProvider
from app.llm.service import build_provider


def _provider_for(monkeypatch, **settings):
    monkeypatch.setattr("app.llm.service.get_settings", lambda: Settings(**settings))
    return build_provider()


def test_mock_is_the_default_provider(monkeypatch):
    assert isinstance(_provider_for(monkeypatch), MockProvider)


def test_gemini_can_be_selected(monkeypatch):
    provider = _provider_for(
        monkeypatch, llm_provider="gemini", gemini_api_key="test-key"
    )
    assert isinstance(provider, GeminiProvider)


def test_ollama_can_be_selected(monkeypatch):
    provider = _provider_for(
        monkeypatch, llm_provider="ollama", ollama_base_url="http://ollama.test"
    )
    assert isinstance(provider, OllamaProvider)


def test_anthropic_requires_an_api_key(monkeypatch):
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        _provider_for(monkeypatch, llm_provider="anthropic")
