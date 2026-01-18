"""Integration tests for the main Anvil class."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from anvil import Anvil, InputParam, Tool


@pytest.fixture
def temp_tools_dir():
    """Create a temporary directory for tool files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "anvil_tools"


@pytest.fixture
def anvil(temp_tools_dir):
    """Create an Anvil instance with temporary directory (using stub generator)."""
    return Anvil(tools_dir=temp_tools_dir, use_stub=True)


class TestAnvilInit:
    def test_creates_tools_directory(self, temp_tools_dir):
        """Anvil creates the tools directory on init."""
        assert not temp_tools_dir.exists()
        Anvil(tools_dir=temp_tools_dir, use_stub=True)
        assert temp_tools_dir.exists()

    def test_default_settings(self, anvil):
        """Default settings are applied."""
        assert anvil.self_healing is True
        assert anvil.max_heal_attempts == 2  # Default is 2 for better self-healing


class TestUseTool:
    def test_use_tool_returns_tool(self, anvil):
        """use_tool returns a Tool object."""
        tool = anvil.use_tool(
            name="test_tool",
            intent="Test the system",
        )

        assert isinstance(tool, Tool)
        assert tool.name == "test_tool"

    def test_use_tool_generates_file(self, anvil, temp_tools_dir):
        """use_tool creates a .py file."""
        anvil.use_tool(
            name="my_tool",
            intent="Do something useful",
            docs_url="https://example.com/docs",
        )

        path = temp_tools_dir / "my_tool.py"
        assert path.exists()

        content = path.read_text()
        assert "ANVIL-MANAGED: true" in content
        assert "def run(" in content

    def test_use_tool_with_same_intent_no_regenerate(self, anvil, temp_tools_dir):
        """use_tool with same intent doesn't regenerate."""
        anvil.use_tool(name="stable", intent="Stable intent")

        path = temp_tools_dir / "stable.py"
        original_content = path.read_text()

        # Call again with same intent
        anvil.use_tool(name="stable", intent="Stable intent")

        # Content should be unchanged
        assert path.read_text() == original_content

    def test_use_tool_different_intent_regenerates(self, anvil, temp_tools_dir):
        """use_tool with different intent regenerates."""
        anvil.use_tool(name="changing", intent="Original intent")

        path = temp_tools_dir / "changing.py"
        original_content = path.read_text()

        # Call with different intent
        anvil.use_tool(name="changing", intent="New different intent")

        # Content should be different
        new_content = path.read_text()
        assert new_content != original_content
        assert "New different intent" in new_content


class TestToolRun:
    def test_run_executes_tool(self, anvil):
        """Tool.run() executes the generated code."""
        tool = anvil.use_tool(
            name="runnable",
            intent="Return test data",
        )

        result = tool.run(query="test")

        assert isinstance(result, dict)
        assert result["tool"] == "runnable"
        assert result["args"] == {"query": "test"}

    def test_run_with_multiple_args(self, anvil):
        """Tool.run() passes all kwargs."""
        tool = anvil.use_tool(name="multi_arg", intent="Handle multiple args")

        result = tool.run(a=1, b=2, c="three")

        assert result["args"] == {"a": 1, "b": 2, "c": "three"}


class TestToolRunSafe:
    def test_run_safe_returns_result(self, anvil):
        """Tool.run_safe() returns ToolResult."""
        tool = anvil.use_tool(name="safe_tool", intent="Safe execution")

        result = tool.run_safe(data="test")

        assert result.success is True
        assert result.data["tool"] == "safe_tool"


class TestEjection:
    def test_user_edited_file_not_overwritten(self, anvil, temp_tools_dir):
        """User-edited files (ejected) are not overwritten."""
        # First, let Anvil create the tool
        anvil.use_tool(name="user_tool", intent="Original intent")

        # Simulate user editing: change ANVIL-MANAGED to false
        path = temp_tools_dir / "user_tool.py"
        content = path.read_text()
        user_content = content.replace("ANVIL-MANAGED: true", "ANVIL-MANAGED: false")
        user_content += "\n# User's custom code here\n"
        path.write_text(user_content)

        # Try to use with different intent
        anvil.use_tool(name="user_tool", intent="Completely different intent")

        # File should still have user's changes
        final_content = path.read_text()
        assert "ANVIL-MANAGED: false" in final_content
        assert "User's custom code here" in final_content

    def test_file_without_header_treated_as_ejected(self, anvil, temp_tools_dir):
        """Files without Anvil header are treated as user-owned."""
        # Create a tool file without header
        path = temp_tools_dir / "manual_tool.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("def run(): return 'manual'\n")

        # Try to use_tool - should NOT overwrite
        anvil.use_tool(name="manual_tool", intent="Some intent")

        # File should be unchanged
        assert path.read_text() == "def run(): return 'manual'\n"


class TestListTools:
    def test_list_tools_empty(self, anvil):
        """list_tools returns empty list initially."""
        assert anvil.list_tools() == []

    def test_list_tools_with_tools(self, anvil):
        """list_tools returns created tools."""
        anvil.use_tool(name="tool_a", intent="Tool A")
        anvil.use_tool(name="tool_b", intent="Tool B")

        tools = anvil.list_tools()
        assert "tool_a" in tools
        assert "tool_b" in tools


class TestGetToolInfo:
    def test_get_tool_info_returns_metadata(self, anvil):
        """get_tool_info returns tool metadata."""
        anvil.use_tool(
            name="info_tool",
            intent="Get info about this",
            docs_url="https://example.com",
        )

        info = anvil.get_tool_info("info_tool")

        assert info is not None
        assert info["name"] == "info_tool"
        assert info["intent"] == "Get info about this"
        assert info["docs_url"] == "https://example.com"

    def test_get_tool_info_missing_tool(self, anvil):
        """get_tool_info returns None for missing tool."""
        assert anvil.get_tool_info("nonexistent") is None


class TestVersioning:
    def test_version_increments_on_regenerate(self, anvil):
        """Version increments when tool is regenerated."""
        anvil.use_tool(name="versioned", intent="Version 1")
        info1 = anvil.get_tool_info("versioned")
        assert info1["version"] == "1.0"

        # Change intent to trigger regeneration
        anvil.use_tool(name="versioned", intent="Version 2 with changes")
        info2 = anvil.get_tool_info("versioned")
        assert info2["version"] == "1.1"

        # Change again
        anvil.use_tool(name="versioned", intent="Version 3 more changes")
        info3 = anvil.get_tool_info("versioned")
        assert info3["version"] == "1.2"


class TestInputSchema:
    def test_use_tool_with_input_params(self, anvil):
        """use_tool accepts InputParam objects."""
        tool = anvil.use_tool(
            name="with_inputs",
            intent="Test with inputs",
            inputs=[
                InputParam(name="query", param_type="str", required=True, description="Search query"),
                InputParam(name="limit", param_type="int", required=False, default=10),
            ],
        )

        assert len(tool.get_inputs()) == 2
        assert tool.get_inputs()[0].name == "query"
        assert tool.get_inputs()[1].default == 10

    def test_use_tool_with_dict_inputs(self, anvil):
        """use_tool accepts dict inputs and converts them."""
        tool = anvil.use_tool(
            name="dict_inputs",
            intent="Test with dict inputs",
            inputs=[
                {"name": "city", "param_type": "str", "required": True},
                {"name": "units", "param_type": "str", "default": "celsius"},
            ],
        )

        assert len(tool.get_inputs()) == 2
        assert tool.get_inputs()[0].name == "city"
        assert tool.get_inputs()[0].required is True
        assert tool.get_inputs()[1].default == "celsius"

    def test_has_required_inputs(self, anvil):
        """has_required_inputs returns True when required inputs exist."""
        tool_with_required = anvil.use_tool(
            name="required_tool",
            intent="Has required",
            inputs=[{"name": "x", "required": True}],
        )
        assert tool_with_required.has_required_inputs() is True

        tool_optional = anvil.use_tool(
            name="optional_tool",
            intent="All optional",
            inputs=[{"name": "y", "required": False, "default": 5}],
        )
        assert tool_optional.has_required_inputs() is False

    def test_tool_without_inputs(self, anvil):
        """Tools without inputs have empty inputs list."""
        tool = anvil.use_tool(name="no_inputs", intent="No inputs needed")
        assert tool.get_inputs() == []
        assert tool.has_required_inputs() is False


class TestTypeCasting:
    def test_cast_int(self, anvil):
        """_cast converts to int."""
        tool = anvil.use_tool(name="cast_test", intent="Test casting")
        assert tool._cast("42", "int") == 42
        assert tool._cast("  100  ", "int") == 100

    def test_cast_float(self, anvil):
        """_cast converts to float."""
        tool = anvil.use_tool(name="cast_test2", intent="Test casting")
        assert tool._cast("3.14", "float") == 3.14
        assert tool._cast("  2.5  ", "float") == 2.5

    def test_cast_bool(self, anvil):
        """_cast converts to bool."""
        tool = anvil.use_tool(name="cast_test3", intent="Test casting")
        assert tool._cast("true", "bool") is True
        assert tool._cast("yes", "bool") is True
        assert tool._cast("1", "bool") is True
        assert tool._cast("false", "bool") is False
        assert tool._cast("no", "bool") is False

    def test_cast_list(self, anvil):
        """_cast converts comma-separated string to list."""
        tool = anvil.use_tool(name="cast_test4", intent="Test casting")
        assert tool._cast("a, b, c", "list") == ["a", "b", "c"]
        assert tool._cast("one,two,three", "list") == ["one", "two", "three"]
        assert tool._cast("  x  ,  y  ", "list") == ["x", "y"]

    def test_cast_str(self, anvil):
        """_cast returns string as-is."""
        tool = anvil.use_tool(name="cast_test5", intent="Test casting")
        assert tool._cast("hello", "str") == "hello"
        assert tool._cast("  spaced  ", "str") == "spaced"


class TestInteractiveMode:
    def test_collect_inputs_empty(self, anvil):
        """_collect_inputs returns empty dict when no inputs defined."""
        tool = anvil.use_tool(name="no_inputs2", intent="No inputs")
        kwargs = tool._collect_inputs()
        assert kwargs == {}

    def test_collect_inputs_required(self, anvil):
        """_collect_inputs prompts for required inputs."""
        tool = anvil.use_tool(
            name="required_inputs",
            intent="Test required",
            inputs=[{"name": "query", "param_type": "str", "required": True}],
        )

        with patch("builtins.input", return_value="test query"):
            kwargs = tool._collect_inputs()

        assert kwargs == {"query": "test query"}

    def test_collect_inputs_with_default(self, anvil):
        """_collect_inputs uses default when input is empty."""
        tool = anvil.use_tool(
            name="default_inputs",
            intent="Test defaults",
            inputs=[{"name": "limit", "param_type": "int", "required": False, "default": 10}],
        )

        # Empty input - should use default
        with patch("builtins.input", return_value=""):
            kwargs = tool._collect_inputs()
        assert kwargs == {"limit": 10}

        # Provided input - should override default
        with patch("builtins.input", return_value="25"):
            kwargs = tool._collect_inputs()
        assert kwargs == {"limit": 25}

    def test_collect_inputs_multiple(self, anvil):
        """_collect_inputs handles multiple inputs."""
        tool = anvil.use_tool(
            name="multi_inputs",
            intent="Multiple inputs",
            inputs=[
                {"name": "city", "param_type": "str", "required": True},
                {"name": "units", "param_type": "str", "required": False, "default": "metric"},
            ],
        )

        with patch("builtins.input", side_effect=["London", ""]):
            kwargs = tool._collect_inputs()

        assert kwargs == {"city": "London", "units": "metric"}

    def test_run_interactive(self, anvil):
        """run_interactive collects inputs and executes."""
        tool = anvil.use_tool(
            name="interactive_tool",
            intent="Interactive test",
            inputs=[{"name": "name", "param_type": "str", "required": True}],
        )

        with patch("builtins.input", return_value="World"):
            result = tool.run_interactive()

        assert result["args"] == {"name": "World"}
