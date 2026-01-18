"""Tests for LLM provider abstraction."""

import pytest
from unittest.mock import MagicMock, patch

from anvil.llm.provider import LLMProvider, LLMResponse, ProviderFactory


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_create_response(self):
        """Test creating an LLMResponse."""
        response = LLMResponse(
            text="Hello, world!",
            model="test-model",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        assert response.text == "Hello, world!"
        assert response.model == "test-model"
        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 5


class TestProviderFactory:
    """Tests for ProviderFactory."""

    def test_list_providers(self):
        """Test that factory has registered providers."""
        providers = ProviderFactory.list_providers()
        # At minimum, anthropic should be registered (we have the package)
        assert isinstance(providers, list)

    def test_unknown_provider_raises(self):
        """Test that unknown provider raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            ProviderFactory.get_provider("unknown_provider", "key", "model")
        assert "Unknown provider" in str(exc_info.value)

    def test_get_anthropic_provider(self):
        """Test getting Anthropic provider."""
        # This will create the provider but not call the API
        provider = ProviderFactory.get_provider("anthropic", "test-key", "claude-3")
        assert provider.provider_name == "anthropic"
        assert provider.api_key == "test-key"
        assert provider.model == "claude-3"

    def test_get_openai_provider(self):
        """Test getting OpenAI provider."""
        provider = ProviderFactory.get_provider("openai", "test-key", "gpt-4")
        assert provider.provider_name == "openai"
        assert provider.api_key == "test-key"
        assert provider.model == "gpt-4"

    def test_get_grok_provider(self):
        """Test getting Grok provider."""
        provider = ProviderFactory.get_provider("grok", "test-key", "grok-2")
        assert provider.provider_name == "grok"
        assert provider.api_key == "test-key"
        assert provider.model == "grok-2"

    def test_provider_aliases(self):
        """Test that provider aliases work."""
        # Claude is alias for Anthropic
        provider1 = ProviderFactory.get_provider("claude", "key", "model")
        assert provider1.provider_name == "anthropic"

        # GPT is alias for OpenAI
        provider2 = ProviderFactory.get_provider("gpt", "key", "model")
        assert provider2.provider_name == "openai"

        # xAI is alias for Grok
        provider3 = ProviderFactory.get_provider("xai", "key", "model")
        assert provider3.provider_name == "grok"


class TestAnthropicProvider:
    """Tests for AnthropicProvider."""

    def test_default_model(self):
        """Test that default model is set."""
        from anvil.llm.anthropic import AnthropicProvider
        provider = AnthropicProvider(api_key="test")
        assert "claude" in provider.model.lower()

    def test_custom_model(self):
        """Test setting custom model."""
        from anvil.llm.anthropic import AnthropicProvider
        provider = AnthropicProvider(api_key="test", model="claude-opus-4")
        assert provider.model == "claude-opus-4"

    def test_provider_name(self):
        """Test provider name property."""
        from anvil.llm.anthropic import AnthropicProvider
        provider = AnthropicProvider(api_key="test")
        assert provider.provider_name == "anthropic"

    @patch("anthropic.Anthropic")
    def test_generate_calls_api(self, mock_anthropic_class):
        """Test that generate calls the Anthropic API."""
        from anvil.llm.anthropic import AnthropicProvider

        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Generated code here")]
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        # Test
        provider = AnthropicProvider(api_key="test-key")
        result = provider.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="Write hello world",
            max_tokens=1000,
        )

        # Verify
        assert result.text == "Generated code here"
        assert result.usage["input_tokens"] == 100
        assert result.usage["output_tokens"] == 50
        mock_client.messages.create.assert_called_once()


class TestOpenAIProvider:
    """Tests for OpenAIProvider."""

    def test_default_model(self):
        """Test that default model is set."""
        from anvil.llm.openai import OpenAIProvider
        provider = OpenAIProvider(api_key="test")
        assert "gpt" in provider.model.lower()

    def test_custom_model(self):
        """Test setting custom model."""
        from anvil.llm.openai import OpenAIProvider
        provider = OpenAIProvider(api_key="test", model="gpt-4-turbo")
        assert provider.model == "gpt-4-turbo"

    def test_provider_name(self):
        """Test provider name property."""
        from anvil.llm.openai import OpenAIProvider
        provider = OpenAIProvider(api_key="test")
        assert provider.provider_name == "openai"

    @patch("openai.OpenAI")
    def test_generate_calls_api(self, mock_openai_class):
        """Test that generate calls the OpenAI API."""
        from anvil.llm.openai import OpenAIProvider

        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Generated code here"
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Test
        provider = OpenAIProvider(api_key="test-key")
        result = provider.generate(
            system_prompt="You are a helpful assistant.",
            user_prompt="Write hello world",
            max_tokens=1000,
        )

        # Verify
        assert result.text == "Generated code here"
        assert result.usage["input_tokens"] == 100
        assert result.usage["output_tokens"] == 50
        mock_client.chat.completions.create.assert_called_once()


class TestGrokProvider:
    """Tests for GrokProvider."""

    def test_default_model(self):
        """Test that default model is set."""
        from anvil.llm.grok import GrokProvider
        provider = GrokProvider(api_key="test")
        assert "grok" in provider.model.lower()

    def test_custom_model(self):
        """Test setting custom model."""
        from anvil.llm.grok import GrokProvider
        provider = GrokProvider(api_key="test", model="grok-3")
        assert provider.model == "grok-3"

    def test_provider_name(self):
        """Test provider name property."""
        from anvil.llm.grok import GrokProvider
        provider = GrokProvider(api_key="test")
        assert provider.provider_name == "grok"

    def test_base_url(self):
        """Test that base URL is set to xAI endpoint."""
        from anvil.llm.grok import GrokProvider
        assert GrokProvider.BASE_URL == "https://api.x.ai/v1"

    @patch("openai.OpenAI")
    def test_generate_uses_openai_client_with_custom_base(self, mock_openai_class):
        """Test that Grok uses OpenAI client with xAI base URL."""
        from anvil.llm.grok import GrokProvider

        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = "Grok response"
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client

        # Test
        provider = GrokProvider(api_key="test-key")
        result = provider.generate(
            system_prompt="System",
            user_prompt="User",
            max_tokens=1000,
        )

        # Verify client was created with xAI base URL
        mock_openai_class.assert_called_once_with(
            api_key="test-key",
            base_url="https://api.x.ai/v1",
        )
        assert result.text == "Grok response"


class TestJITGeneratorWithProviders:
    """Tests for JITGenerator with different providers."""

    def test_default_provider_is_anthropic(self):
        """Test that default provider is Anthropic."""
        from anvil.jit_generator import JITGenerator
        gen = JITGenerator(api_key="test")
        assert gen.provider_name == "anthropic"

    def test_openai_provider(self):
        """Test using OpenAI provider."""
        from anvil.jit_generator import JITGenerator
        gen = JITGenerator(api_key="test", provider="openai")
        assert gen.provider_name == "openai"
        assert "gpt" in gen.model.lower()

    def test_grok_provider(self):
        """Test using Grok provider."""
        from anvil.jit_generator import JITGenerator
        gen = JITGenerator(api_key="test", provider="grok")
        assert gen.provider_name == "grok"
        assert "grok" in gen.model.lower()

    def test_custom_model_override(self):
        """Test that custom model overrides default."""
        from anvil.jit_generator import JITGenerator
        gen = JITGenerator(api_key="test", provider="openai", model="gpt-4-turbo")
        assert gen.model == "gpt-4-turbo"


class TestAnvilWithProviders:
    """Tests for Anvil class with different providers."""

    def test_default_provider(self, tmp_path):
        """Test that Anvil defaults to anthropic."""
        from anvil import Anvil
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        # StubGenerator doesn't use providers, but we can check it was set
        assert anvil.provider == "anthropic"

    def test_openai_provider(self, tmp_path):
        """Test Anvil with OpenAI provider."""
        from anvil import Anvil
        anvil = Anvil(tools_dir=tmp_path, use_stub=True, provider="openai")
        assert anvil.provider == "openai"

    def test_grok_provider(self, tmp_path):
        """Test Anvil with Grok provider."""
        from anvil import Anvil
        anvil = Anvil(tools_dir=tmp_path, use_stub=True, provider="grok")
        assert anvil.provider == "grok"

    def test_provider_case_insensitive(self, tmp_path):
        """Test that provider name is case-insensitive."""
        from anvil import Anvil
        anvil = Anvil(tools_dir=tmp_path, use_stub=True, provider="OpenAI")
        assert anvil.provider == "openai"
