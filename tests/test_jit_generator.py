"""Tests for JIT Generator."""

import pytest

from anvil.jit_generator import JITGenerator, StubJITGenerator, _extract_code
from anvil.generators.local import LocalGenerator
from anvil.models import ToolConfig


class TestExtractCode:
    def test_extract_python_code_block(self):
        """Extracts code from python code block."""
        text = """Here's the code:
```python
def run():
    return 42
```
That's it!"""
        result = _extract_code(text)
        assert result == "def run():\n    return 42"

    def test_extract_generic_code_block(self):
        """Extracts code from generic code block."""
        text = """```
def run():
    pass
```"""
        result = _extract_code(text)
        assert result == "def run():\n    pass"

    def test_no_code_block(self):
        """Returns raw text if no code block."""
        text = "def run(): pass"
        result = _extract_code(text)
        assert result == "def run(): pass"


class TestStubJITGenerator:
    def test_generate_returns_code(self):
        """generate() returns GeneratedCode with valid Python."""
        generator = StubJITGenerator()
        config = ToolConfig(
            name="search_notion",
            intent="Search the Notion workspace",
            docs_url="https://developers.notion.com",
        )

        result = generator.generate(config)

        assert result.code is not None
        assert len(result.code) > 0
        assert "def run(" in result.code

    def test_generate_includes_intent_in_docstring(self):
        """Generated code includes the intent as documentation."""
        generator = StubJITGenerator()
        config = ToolConfig(
            name="send_slack",
            intent="Send a message to Slack",
        )

        result = generator.generate(config)

        assert "Send a message to Slack" in result.code

    def test_generate_code_is_executable(self):
        """Generated code can be compiled and executed."""
        generator = StubJITGenerator()
        config = ToolConfig(
            name="test_tool",
            intent="Test the system",
        )

        result = generator.generate(config)

        # Compile the code
        compiled = compile(result.code, "<string>", "exec")
        assert compiled is not None

        # Execute and get the run function
        namespace: dict = {}
        exec(compiled, namespace)

        assert "run" in namespace
        run_fn = namespace["run"]

        # Call the run function
        output = run_fn(query="test")
        assert output["tool"] == "test_tool"
        assert output["args"] == {"query": "test"}

    def test_generate_with_no_docs_url(self):
        """Works without docs_url."""
        generator = StubJITGenerator()
        config = ToolConfig(
            name="simple",
            intent="Do something simple",
        )

        result = generator.generate(config)

        assert "def run(" in result.code
        assert "None" in result.code  # docs_url shows as None

    def test_generate_escapes_quotes_in_intent(self):
        """Intent with quotes is properly escaped."""
        generator = StubJITGenerator()
        config = ToolConfig(
            name="quoted",
            intent='Search for "important" items',
        )

        result = generator.generate(config)

        # Should compile without syntax errors
        compiled = compile(result.code, "<string>", "exec")
        assert compiled is not None

    def test_generate_fix_returns_stub(self):
        """generate_fix returns stub code."""
        generator = StubJITGenerator()
        config = ToolConfig(name="broken", intent="Fix this")

        result = generator.generate_fix(
            config=config,
            previous_code="def run(): raise Exception('broken')",
            error_message="Exception: broken",
        )

        assert "def run(" in result.code

    def test_fetch_documentation_returns_stub(self):
        """fetch_documentation returns stub text."""
        generator = StubJITGenerator()

        result = generator.fetch_documentation("https://example.com")

        assert "https://example.com" in result


class TestJITGeneratorInit:
    def test_lazy_loads_provider(self):
        """Provider is not loaded until needed."""
        generator = JITGenerator(api_key="test-key")
        assert generator._provider is None

    def test_requires_api_key(self):
        """Raises error if no API key provided."""
        generator = JITGenerator()  # No key

        with pytest.raises(ValueError, match="API key required"):
            generator._get_provider()

    def test_firecrawl_optional(self):
        """FireCrawl returns None if no key."""
        generator = JITGenerator(api_key="test")

        result = generator._get_firecrawl()
        assert result is None


class TestDependencyDetection:
    def test_detects_requests(self):
        """Detects requests import."""
        generator = LocalGenerator(api_key="test-key")
        code = "import requests\ndef run(): pass"

        deps = generator._detect_dependencies(code)
        assert "requests" in deps

    def test_detects_from_import(self):
        """Detects from X import Y."""
        generator = LocalGenerator(api_key="test-key")
        code = "from bs4 import BeautifulSoup\ndef run(): pass"

        deps = generator._detect_dependencies(code)
        assert "beautifulsoup4" in deps

    def test_no_false_positives(self):
        """Doesn't detect stdlib modules."""
        generator = LocalGenerator(api_key="test-key")
        code = "import os\nimport json\ndef run(): pass"

        deps = generator._detect_dependencies(code)
        assert len(deps) == 0
