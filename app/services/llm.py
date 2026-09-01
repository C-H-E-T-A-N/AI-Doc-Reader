"""
LLM service: a constructed Prompt -> a generated answer, via Anthropic
Claude by default, or Gemini (settings.llm_provider = "gemini").

Same "one seam" pattern as embeddings.py: LLMProvider is the only place
a provider SDK (`anthropic` or `google.genai`) is imported. Nothing
else in the app -- not the routes, not the prompt builder -- talks to a
provider SDK directly. Swapping models, providers, or adding streaming
later touches only this file.
"""

from abc import ABC, abstractmethod

import anthropic
from anthropic import Anthropic
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types

from app.config import settings
from app.services.exceptions import ConfigurationError
from app.services.prompt_builder import Prompt


class LLMGenerationError(Exception):
    """Raised when the LLM provider fails (network, rate limit, auth, bad request, ...)."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: Prompt) -> str:
        """Send the prompt to the model and return the generated answer text."""


class AnthropicLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024):
        if not api_key:
            raise ConfigurationError(
                "ANTHROPIC_API_KEY is not set. LLM generation requires it -- add it to your .env file."
            )
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, prompt: Prompt) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=prompt.system,
                messages=[{"role": "user", "content": prompt.user}],
            )
        except anthropic.AnthropicError as e:
            raise LLMGenerationError(f"LLM request failed: {e}") from e
        return response.content[0].text


class GeminiLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, max_tokens: int = 1024):
        if not api_key:
            raise ConfigurationError(
                "GEMINI_API_KEY is not set. LLM generation requires it -- add it to your .env file."
            )
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, prompt: Prompt) -> str:
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=prompt.user,
                config=genai_types.GenerateContentConfig(
                    system_instruction=prompt.system,
                    max_output_tokens=self._max_tokens,
                ),
            )
        except genai_errors.APIError as e:
            raise LLMGenerationError(f"LLM request failed: {e}") from e
        return response.text


def _default_llm_provider() -> LLMProvider:
    if settings.llm_provider == "gemini":
        return GeminiLLMProvider(api_key=settings.gemini_api_key, model=settings.gemini_llm_model)
    return AnthropicLLMProvider(api_key=settings.anthropic_api_key, model=settings.llm_model)


class LLMService:
    def __init__(self, provider: LLMProvider | None = None):
        self._provider = provider or _default_llm_provider()

    def generate(self, prompt: Prompt) -> str:
        return self._provider.generate(prompt)
