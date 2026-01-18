"""Tests for ToolManager - file operations and header protocol."""

import tempfile
from pathlib import Path

import pytest

from anvil.models import ToolConfig, ToolStatus
from anvil.tool_manager import (
    HEADER_TEMPLATE,
    HeaderInfo,
    ToolManager,
    compute_intent_hash,
)


@pytest.fixture
def temp_tools_dir():
    """Create a temporary directory for tool files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "anvil_tools"


@pytest.fixture
def manager(temp_tools_dir):
    """Create a ToolManager with temporary directory."""
    return ToolManager(tools_dir=temp_tools_dir)


class TestComputeIntentHash:
    def test_deterministic(self):
        """Same intent produces same hash."""
        intent = "Search Notion workspace"
        hash1 = compute_intent_hash(intent)
        hash2 = compute_intent_hash(intent)
        assert hash1 == hash2

    def test_different_intents(self):
        """Different intents produce different hashes."""
        hash1 = compute_intent_hash("Search Notion")
        hash2 = compute_intent_hash("Send Slack message")
        assert hash1 != hash2

    def test_hash_length(self):
        """Hash is 8 characters."""
        hash = compute_intent_hash("test")
        assert len(hash) == 8


class TestToolManagerInit:
    def test_creates_directory(self, temp_tools_dir):
        """ToolManager creates the tools directory."""
        assert not temp_tools_dir.exists()
        ToolManager(tools_dir=temp_tools_dir)
        assert temp_tools_dir.exists()

    def test_creates_init_file(self, temp_tools_dir):
        """ToolManager creates __init__.py."""
        ToolManager(tools_dir=temp_tools_dir)
        init_file = temp_tools_dir / "__init__.py"
        assert init_file.exists()

    def test_creates_registry(self, temp_tools_dir):
        """ToolManager creates tool_registry.json."""
        ToolManager(tools_dir=temp_tools_dir)
        registry = temp_tools_dir / "tool_registry.json"
        assert registry.exists()


class TestToolManagerPaths:
    def test_get_tool_path(self, manager):
        """get_tool_path returns correct path."""
        path = manager.get_tool_path("search_notion")
        assert path.name == "search_notion.py"
        assert path.parent == manager.tools_dir

    def test_tool_exists_false(self, manager):
        """tool_exists returns False for missing tool."""
        assert manager.tool_exists("nonexistent") is False

    def test_tool_exists_true(self, manager):
        """tool_exists returns True for existing tool."""
        path = manager.get_tool_path("test_tool")
        path.write_text("# test")
        assert manager.tool_exists("test_tool") is True


class TestHeaderParsing:
    def test_parse_header_no_file(self, manager):
        """parse_header returns None for missing file."""
        result = manager.parse_header("nonexistent")
        assert result is None

    def test_parse_header_managed_true(self, manager):
        """parse_header correctly parses managed=true header."""
        path = manager.get_tool_path("test_tool")
        content = HEADER_TEMPLATE.format(managed="true", version="1.0", hash="abc12345")
        content += "def run(): pass"
        path.write_text(content)

        result = manager.parse_header("test_tool")
        assert result is not None
        assert result.is_managed is True
        assert result.version == "1.0"
        assert result.hash == "abc12345"

    def test_parse_header_managed_false(self, manager):
        """parse_header correctly parses managed=false header."""
        path = manager.get_tool_path("test_tool")
        content = HEADER_TEMPLATE.format(managed="false", version="2.0", hash="xyz99999")
        content += "def run(): pass"
        path.write_text(content)

        result = manager.parse_header("test_tool")
        assert result is not None
        assert result.is_managed is False
        assert result.version == "2.0"

    def test_parse_header_no_header(self, manager):
        """parse_header returns unmanaged for file without header."""
        path = manager.get_tool_path("test_tool")
        path.write_text("def run():\n    return 42")

        result = manager.parse_header("test_tool")
        assert result is not None
        assert result.is_managed is False


class TestIsManaged:
    def test_is_managed_no_file(self, manager):
        """is_managed returns False for missing file."""
        assert manager.is_managed("nonexistent") is False

    def test_is_managed_true(self, manager):
        """is_managed returns True for managed file."""
        path = manager.get_tool_path("test")
        path.write_text("# ANVIL-MANAGED: true\n# version: 1.0\n# hash: abc\n")
        assert manager.is_managed("test") is True

    def test_is_managed_false(self, manager):
        """is_managed returns False for ejected file."""
        path = manager.get_tool_path("test")
        path.write_text("# ANVIL-MANAGED: false\n# version: 1.0\n# hash: abc\n")
        assert manager.is_managed("test") is False


class TestShouldRegenerate:
    def test_should_regenerate_no_file(self, manager):
        """should_regenerate returns True for missing file."""
        assert manager.should_regenerate("new_tool", "some intent") is True

    def test_should_regenerate_not_managed(self, manager):
        """should_regenerate returns False for user-owned file."""
        path = manager.get_tool_path("test")
        path.write_text("def run(): pass")  # No header
        assert manager.should_regenerate("test", "any intent") is False

    def test_should_regenerate_same_intent(self, manager):
        """should_regenerate returns False if intent unchanged."""
        intent = "Search Notion"
        hash = compute_intent_hash(intent)
        path = manager.get_tool_path("test")
        path.write_text(f"# ANVIL-MANAGED: true\n# version: 1.0\n# hash: {hash}\n")

        assert manager.should_regenerate("test", intent) is False

    def test_should_regenerate_different_intent(self, manager):
        """should_regenerate returns True if intent changed."""
        path = manager.get_tool_path("test")
        path.write_text("# ANVIL-MANAGED: true\n# version: 1.0\n# hash: oldhash1\n")

        assert manager.should_regenerate("test", "New different intent") is True


class TestWriteTool:
    def test_write_tool_creates_file(self, manager):
        """write_tool creates the tool file."""
        config = ToolConfig(name="test", intent="Test intent")
        code = "def run():\n    return 42"

        path = manager.write_tool("test", code, config)

        assert path.exists()
        content = path.read_text()
        assert "ANVIL-MANAGED: true" in content
        assert "def run():" in content

    def test_write_tool_includes_hash(self, manager):
        """write_tool includes intent hash in header."""
        config = ToolConfig(name="test", intent="Test intent")
        expected_hash = compute_intent_hash("Test intent")

        manager.write_tool("test", "def run(): pass", config)

        content = manager.get_tool_path("test").read_text()
        assert f"# hash: {expected_hash}" in content

    def test_write_tool_updates_registry(self, manager):
        """write_tool updates the registry."""
        config = ToolConfig(name="my_tool", intent="Do something", docs_url="https://example.com")
        manager.write_tool("my_tool", "def run(): pass", config)

        metadata = manager.get_metadata("my_tool")
        assert metadata is not None
        assert metadata.name == "my_tool"
        assert metadata.intent == "Do something"
        assert metadata.docs_url == "https://example.com"
        assert metadata.status == ToolStatus.ACTIVE


class TestReadToolCode:
    def test_read_tool_code_no_file(self, manager):
        """read_tool_code returns None for missing file."""
        assert manager.read_tool_code("nonexistent") is None

    def test_read_tool_code_strips_header(self, manager):
        """read_tool_code returns code without header."""
        config = ToolConfig(name="test", intent="Test")
        code = "def run():\n    return 42"
        manager.write_tool("test", code, config)

        result = manager.read_tool_code("test")
        assert result is not None
        assert "ANVIL-MANAGED" not in result
        assert "def run():" in result

    def test_read_tool_code_no_header(self, manager):
        """read_tool_code works with files without header."""
        path = manager.get_tool_path("test")
        path.write_text("def run():\n    return 99")

        result = manager.read_tool_code("test")
        assert result == "def run():\n    return 99"
