"""Anthropic (Claude) LLM provider."""

from typing import Any

from anvil.llm.provider import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider.

    Supports Claude models via the Anthropic API.

    Default model: claude-sonnet-4-20250514
    """

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, api_key: str, model: str | None = None):
        """Initialize the Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model to use (defaults to claude-sonnet-4-20250514)
        """
        super().__init__(api_key, model or self.DEFAULT_MODEL)

    @property
    def provider_name(self) -> str:
        return "anthropic"

    def _get_client(self) -> Any:
        """Get or create the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                )
            self._client = Anthropic(api_key=self.api_key)
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        """Generate a response using Claude.

        Args:
            system_prompt: System instructions
            user_prompt: User message
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with generated text
        """
        client = self._get_client()

        response = client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        return LLMResponse(
            text=response.content[0].text,
            model=self.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
        )
