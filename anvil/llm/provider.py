"""Abstract LLM provider interface and factory."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Normalized response from any LLM provider."""

    text: str
    model: str
    usage: dict[str, int]


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    All providers must implement the generate() method with a consistent interface.
    """

    def __init__(self, api_key: str, model: str):
        """Initialize the provider.

        Args:
            api_key: API key for the provider
            model: Model identifier to use
        """
        self.api_key = api_key
        self.model = model
        self._client: Any = None

    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            system_prompt: System instructions for the model
            user_prompt: User message/query
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with text, model, and usage info
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'anthropic', 'openai', 'grok')."""
        pass


class ProviderFactory:
    """Factory for creating LLM provider instances."""

    _providers: dict[str, type[LLMProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_class: type[LLMProvider]) -> None:
        """Register a provider class.

        Args:
            name: Provider name (e.g., 'anthropic', 'openai')
            provider_class: The provider class to register
        """
        cls._providers[name.lower()] = provider_class

    @classmethod
    def get_provider(
        cls,
        provider_name: str,
        api_key: str,
        model: str,
    ) -> LLMProvider:
        """Get a provider instance.

        Args:
            provider_name: Name of the provider ('anthropic', 'openai', 'grok')
            api_key: API key for the provider
            model: Model identifier

        Returns:
            LLMProvider instance

        Raises:
            ValueError: If provider is not registered
        """
        name = provider_name.lower()
        if name not in cls._providers:
            available = ", ".join(cls._providers.keys()) or "none"
            raise ValueError(
                f"Unknown provider: {provider_name}. Available: {available}"
            )
        return cls._providers[name](api_key=api_key, model=model)

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names."""
        return list(cls._providers.keys())


# Import and register providers (done at module load time)
def _register_providers() -> None:
    """Register all available providers."""
    # Anthropic
    try:
        from anvil.llm.anthropic import AnthropicProvider
        ProviderFactory.register("anthropic", AnthropicProvider)
        ProviderFactory.register("claude", AnthropicProvider)  # Alias
    except ImportError:
        pass

    # OpenAI
    try:
        from anvil.llm.openai import OpenAIProvider
        ProviderFactory.register("openai", OpenAIProvider)
        ProviderFactory.register("gpt", OpenAIProvider)  # Alias
    except ImportError:
        pass

    # Grok (xAI)
    try:
        from anvil.llm.grok import GrokProvider
        ProviderFactory.register("grok", GrokProvider)
        ProviderFactory.register("xai", GrokProvider)  # Alias
    except ImportError:
        pass


# Register on import
_register_providers()


def get_provider(
    provider_name: str,
    api_key: str,
    model: str,
) -> LLMProvider:
    """Convenience function to get a provider.

    Args:
        provider_name: Name of the provider
        api_key: API key
        model: Model identifier

    Returns:
        LLMProvider instance
    """
    return ProviderFactory.get_provider(provider_name, api_key, model)
