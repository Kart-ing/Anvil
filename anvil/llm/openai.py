"""OpenAI (GPT) LLM provider."""

from typing import Any

from anvil.llm.provider import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider.

    Supports GPT models via the OpenAI API.

    Default model: gpt-4o
    """

    DEFAULT_MODEL = "gpt-4o"

    def __init__(self, api_key: str, model: str | None = None):
        """Initialize the OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model to use (defaults to gpt-4o)
        """
        super().__init__(api_key, model or self.DEFAULT_MODEL)

    @property
    def provider_name(self) -> str:
        return "openai"

    def _get_client(self) -> Any:
        """Get or create the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "openai package not installed. "
                    "Install with: pip install openai"
                )
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        """Generate a response using GPT.

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
