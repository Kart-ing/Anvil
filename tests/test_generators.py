"""Tests for the generator architecture (Local, Stub modes)."""

import pytest

from anvil import Anvil
from anvil.generators import (
    BaseGenerator,
    GeneratorMode,
    LocalGenerator,
    StubGenerator,
)
from anvil.jit_generator import get_generator, JITGenerator, StubJITGenerator
from anvil.models import GeneratedCode, ToolConfig


class TestGeneratorMode:
    """Tests for GeneratorMode enum."""

    def test_mode_values(self):
        """Test that all modes have correct values."""
        assert GeneratorMode.LOCAL == "local"
        assert GeneratorMode.STUB == "stub"

    def test_mode_string_compatibility(self):
        """Test that modes can be compared to strings."""
        assert GeneratorMode.LOCAL == "local"
        assert GeneratorMode.STUB == "stub"


class TestStubGenerator:
    """Tests for StubGenerator."""

    def test_mode_is_stub(self):
        """Test that StubGenerator has stub mode."""
        gen = StubGenerator()
        assert gen.mode == GeneratorMode.STUB

    def test_fetch_documentation(self):
        """Test stub documentation fetching."""
        gen = StubGenerator()
        docs = gen.fetch_documentation("https://example.com/docs")
        assert "Stub documentation" in docs
        assert "https://example.com/docs" in docs

    def test_fetch_documentation_no_url(self):
        """Test stub documentation with no URL."""
        gen = StubGenerator()
        docs = gen.fetch_documentation(None)
        assert "Stub documentation" in docs
        assert "no URL" in docs

    def test_generate(self):
        """Test stub code generation."""
        gen = StubGenerator()
        config = ToolConfig(name="test_tool", intent="Test the tool")
        result = gen.generate(config)

        assert isinstance(result, GeneratedCode)
        assert "test_tool" in result.code
        assert "Test the tool" in result.code
        assert "stub_execution" in result.code
        assert result.dependencies == []

    def test_generate_fix(self):
        """Test stub generate_fix returns same as generate."""
        gen = StubGenerator()
        config = ToolConfig(name="fix_tool", intent="Fix something")
        result = gen.generate_fix(config, "old code", "error message")

        assert isinstance(result, GeneratedCode)
        assert "fix_tool" in result.code

    def test_ignores_kwargs(self):
        """Test that StubGenerator ignores constructor kwargs."""
        # Should not raise
        gen = StubGenerator(api_key="ignored", model="ignored", extra="ignored")
        assert gen.mode == GeneratorMode.STUB


class TestLocalGenerator:
    """Tests for LocalGenerator."""

    def test_mode_is_local(self):
        """Test that LocalGenerator has local mode."""
        gen = LocalGenerator(api_key="test-key")
        assert gen.mode == GeneratorMode.LOCAL

    def test_default_provider_is_anthropic(self):
        """Test that default provider is Anthropic."""
        gen = LocalGenerator(api_key="test-key")
        assert gen.provider_name == "anthropic"

    def test_custom_provider(self):
        """Test using a custom provider."""
        gen = LocalGenerator(api_key="test-key", provider="openai")
        assert gen.provider_name == "openai"

    def test_custom_model(self):
        """Test using a custom model."""
        gen = LocalGenerator(api_key="test-key", model="gpt-4o")
        assert gen.model == "gpt-4o"

    def test_stores_api_key(self):
        """Test that LocalGenerator stores the API key."""
        gen = LocalGenerator(api_key="my-test-key")
        assert gen.api_key == "my-test-key"


class TestGetGeneratorFactory:
    """Tests for get_generator factory function."""

    def test_stub_mode(self):
        """Test getting stub generator."""
        gen = get_generator(mode="stub")
        assert isinstance(gen, StubGenerator)
        assert gen.mode == GeneratorMode.STUB

    def test_local_mode(self):
        """Test getting local generator."""
        gen = get_generator(mode="local", api_key="test-key")
        assert isinstance(gen, LocalGenerator)
        assert gen.mode == GeneratorMode.LOCAL

    def test_default_mode_is_local(self):
        """Test that default mode is local."""
        gen = get_generator(api_key="test-key")
        assert isinstance(gen, LocalGenerator)

    def test_case_insensitive_mode(self):
        """Test that mode is case insensitive."""
        gen = get_generator(mode="STUB")
        assert isinstance(gen, StubGenerator)

        gen = get_generator(mode="Stub")
        assert isinstance(gen, StubGenerator)

    def test_cloud_mode_requires_package(self):
        """Test that cloud mode raises ImportError without anvil-cloud."""
        with pytest.raises(ImportError, match="anvil-cloud"):
            get_generator(mode="cloud")


class TestBackwardCompatibility:
    """Tests for backward compatible aliases."""

    def test_jit_generator_alias(self):
        """Test that JITGenerator is alias for LocalGenerator."""
        assert JITGenerator is LocalGenerator

    def test_stub_jit_generator_alias(self):
        """Test that StubJITGenerator is alias for StubGenerator."""
        assert StubJITGenerator is StubGenerator

    def test_import_from_jit_generator(self):
        """Test backward compatible imports from jit_generator."""
        from anvil.jit_generator import (
            JITGenerator,
            StubJITGenerator,
            BaseGenerator,
            GeneratorMode,
            get_generator,
        )

        assert JITGenerator is LocalGenerator
        assert StubJITGenerator is StubGenerator


class TestAnvilModeParameter:
    """Tests for Anvil mode parameter integration."""

    def test_default_mode_with_stub(self, tmp_path):
        """Test that use_stub=True creates StubGenerator."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        assert isinstance(anvil._generator, StubGenerator)

    def test_explicit_stub_mode(self, tmp_path):
        """Test explicit stub mode."""
        anvil = Anvil(tools_dir=tmp_path, mode="stub")
        assert isinstance(anvil._generator, StubGenerator)

    def test_local_mode_explicit(self, tmp_path):
        """Test explicit local mode."""
        anvil = Anvil(tools_dir=tmp_path, mode="local", api_key="test-key")
        assert isinstance(anvil._generator, LocalGenerator)

    def test_tool_generation_with_stub(self, tmp_path):
        """Test that tool generation works with stub mode."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        tool = anvil.use_tool(name="test_tool", intent="Test intent")

        result = tool.run()
        assert result["status"] == "stub_execution"
        assert result["tool"] == "test_tool"

    def test_cloud_mode_requires_package(self, tmp_path):
        """Test that cloud mode raises ImportError without anvil-cloud."""
        with pytest.raises(ImportError, match="anvil-cloud"):
            Anvil(tools_dir=tmp_path, mode="cloud")


class TestGeneratorModeProperty:
    """Tests for generator mode property on Anvil."""

    def test_anvil_mode_property_stub(self, tmp_path):
        """Test that Anvil exposes mode property with stub."""
        anvil = Anvil(tools_dir=tmp_path, use_stub=True)
        assert anvil.mode == "local"  # default mode
        assert isinstance(anvil._generator, StubGenerator)

    def test_anvil_mode_explicit_stub(self, tmp_path):
        """Test that Anvil mode=stub works."""
        anvil = Anvil(tools_dir=tmp_path, mode="stub")
        assert anvil.mode == "stub"
        assert isinstance(anvil._generator, StubGenerator)

    def test_anvil_mode_local(self, tmp_path):
        """Test mode property with local generator."""
        anvil = Anvil(tools_dir=tmp_path, mode="local", api_key="key")
        assert anvil.mode == "local"
        assert isinstance(anvil._generator, LocalGenerator)
