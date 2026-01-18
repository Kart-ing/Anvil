"""Grok (xAI) LLM provider."""

from typing import Any

from anvil.llm.provider import LLMProvider, LLMResponse


class GrokProvider(LLMProvider):
    """xAI Grok provider.

    Supports Grok models via the xAI API.
    Uses OpenAI-compatible endpoint at api.x.ai.

    Default model: grok-2-latest
    """

    DEFAULT_MODEL = "grok-2-latest"
    BASE_URL = "https://api.x.ai/v1"

    def __init__(self, api_key: str, model: str | None = None):
        """Initialize the Grok provider.

        Args:
            api_key: xAI API key (XAI_API_KEY)
            model: Model to use (defaults to grok-2-latest)
        """
        super().__init__(api_key, model or self.DEFAULT_MODEL)

    @property
    def provider_name(self) -> str:
        return "grok"

    def _get_client(self) -> Any:
        """Get or create the Grok client.

        Uses OpenAI client with xAI base URL since Grok uses
        an OpenAI-compatible API.
        """
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "openai package not installed. "
                    "Grok uses OpenAI-compatible API. "
                    "Install with: pip install openai"
                )
            self._client = OpenAI(
                api_key=self.api_key,
                base_url=self.BASE_URL,
            )
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        """Generate a response using Grok.

        Args:
            system_prompt: System instructions
            user_prompt: User message
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with generated text
        """
        client = self._get_client()

        response = client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        return LLMResponse(
            text=response.choices[0].message.content or "",
            model=self.model,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        )
