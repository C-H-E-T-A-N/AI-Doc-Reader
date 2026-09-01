"""
Shared exception types for translating provider/config failures into
clean HTTP responses at the route layer, instead of routes needing to
know about `openai`/`anthropic`/`chromadb` internals, and instead of a
raw SDK exception (with its message, and sometimes internal details)
reaching the API client directly.

ConfigurationError subclasses ValueError so existing `pytest.raises(ValueError)`
checks from earlier stages keep working -- a missing API key is a kind
of invalid configuration value.
"""


class ConfigurationError(ValueError):
    """Raised when required configuration (e.g. an API key) is missing or invalid."""
