"""
LLM service: a constructed Prompt -> a generated answer, via Anthropic Claude.

Same "one seam" pattern as embeddings.py: LLMProvider is the only place
the `anthropic` SDK is imported. Nothing else in the app -- not the
routes, not the prompt builder -- talks to the provider SDK directly.
Swapping models, providers, or adding streaming later touches only this
file.
"""

from abc import ABC, abstractmethod

from anthropic import Anthropic

from app.config import settings
from app.services.prompt_builder import Prompt


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: Prompt) -> str:
        """Send the prompt to the model and return the generated answer text."""


class AnthropicLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024):
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. LLM generation requires it -- add it to your .env file."
            )
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, prompt: Prompt) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=prompt.system,
            messages=[{"role": "user", "content": prompt.user}],
        )
        return response.content[0].text


class LLMService:
    def __init__(self, provider: LLMProvider | None = None):
        self._provider = provider or AnthropicLLMProvider(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
        )

    def generate(self, prompt: Prompt) -> str:
        return self._provider.generate(prompt)
