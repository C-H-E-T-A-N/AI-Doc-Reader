import pytest

from app.config import settings
from app.services.llm import (
    AnthropicLLMProvider,
    GeminiLLMProvider,
    LLMProvider,
    LLMService,
    OpenAILLMProvider,
    _default_llm_provider,
)
from app.services.prompt_builder import Prompt


class FakeLLMProvider(LLMProvider):
    def __init__(self, response: str = "fake answer"):
        self.response = response
        self.received_prompts: list[Prompt] = []

    def generate(self, prompt: Prompt) -> str:
        self.received_prompts.append(prompt)
        return self.response


def test_llm_service_delegates_to_its_provider():
    provider = FakeLLMProvider(response="Employees get 24 paid leaves per year.")
    service = LLMService(provider=provider)

    answer = service.generate(Prompt(system="sys", user="user question"))

    assert answer == "Employees get 24 paid leaves per year."
    assert len(provider.received_prompts) == 1
    assert provider.received_prompts[0].user == "user question"


def test_anthropic_provider_requires_an_api_key():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        AnthropicLLMProvider(api_key="", model="claude-sonnet-5")


def test_gemini_provider_requires_an_api_key():
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiLLMProvider(api_key="", model="gemini-2.5-flash")


def test_openai_provider_requires_an_api_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAILLMProvider(api_key="", model="gpt-4o-mini")


@pytest.mark.parametrize(
    ("provider", "expected"),
    [
        ("anthropic", AnthropicLLMProvider),
        ("gemini", GeminiLLMProvider),
        ("openai", OpenAILLMProvider),
    ],
)
def test_default_llm_provider_follows_the_llm_provider_setting(provider, expected, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", provider)
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_api_key", "test-key")

    assert isinstance(_default_llm_provider(), expected)
