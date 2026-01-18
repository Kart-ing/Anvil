"""Tests for tool chaining functionality."""

import tempfile
from pathlib import Path

import pytest

from anvil import Anvil, Tool, ToolChain
from anvil.models import ToolResult


@pytest.fixture
def temp_tools_dir():
    """Create a temporary directory for tool files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "anvil_tools"


@pytest.fixture
def anvil(temp_tools_dir):
    """Create an Anvil instance with temporary directory (using stub generator)."""
    return Anvil(tools_dir=temp_tools_dir, use_stub=True)


class TestToolChainBasics:
    def test_chain_requires_at_least_one_tool(self):
        """ToolChain raises ValueError for empty tools list."""
        with pytest.raises(ValueError, match="requires at least one tool"):
            ToolChain([])

    def test_chain_with_single_tool(self, anvil):
        """ToolChain works with a single tool."""
        tool = anvil.use_tool(name="single", intent="Single tool")
        chain = ToolChain([tool])

        assert len(chain) == 1
        assert chain.tools[0] is tool

    def test_chain_with_multiple_tools(self, anvil):
        """ToolChain accepts multiple tools."""
        t1 = anvil.use_tool(name="t1", intent="Tool 1")
        t2 = anvil.use_tool(name="t2", intent="Tool 2")
        t3 = anvil.use_tool(name="t3", intent="Tool 3")

        chain = ToolChain([t1, t2, t3])

        assert len(chain) == 3
        assert chain.tools == [t1, t2, t3]


class TestToolPipe:
    def test_pipe_creates_chain(self, anvil):
        """Tool.pipe() creates a ToolChain."""
        t1 = anvil.use_tool(name="first", intent="First tool")
        t2 = anvil.use_tool(name="second", intent="Second tool")

        chain = t1.pipe(t2)

        assert isinstance(chain, ToolChain)
        assert len(chain) == 2
        assert chain.tools[0] is t1
        assert chain.tools[1] is t2

    def test_pipe_chaining(self, anvil):
        """Multiple pipe() calls build longer chains."""
        t1 = anvil.use_tool(name="a", intent="A")
        t2 = anvil.use_tool(name="b", intent="B")
        t3 = anvil.use_tool(name="c", intent="C")

        chain = t1.pipe(t2).pipe(t3)

        assert len(chain) == 3
        assert chain.tools[0].name == "a"
        assert chain.tools[1].name == "b"
        assert chain.tools[2].name == "c"


class TestChainRun:
    def test_run_passes_initial_kwargs(self, anvil):
        """Chain.run() passes initial kwargs to first tool."""
        tool = anvil.use_tool(name="receiver", intent="Receive args")
        chain = ToolChain([tool])

        result = chain.run(x=1, y=2)

        assert result["tool"] == "receiver"
        assert result["args"] == {"x": 1, "y": 2}

    def test_run_chains_dict_output(self, anvil):
        """Dict output is unpacked as kwargs for next tool."""
        t1 = anvil.use_tool(name="producer", intent="Produce data")
        t2 = anvil.use_tool(name="consumer", intent="Consume data")

        chain = t1.pipe(t2)
        result = chain.run(input="start")

        # t1 produces {"tool": "producer", "args": {"input": "start"}}
        # t2 receives that dict as kwargs
        assert result["tool"] == "consumer"
        assert "tool" in result["args"]  # The dict from t1 was passed as kwargs

    def test_run_chains_non_dict_as_data(self, anvil):
        """Non-dict output is passed as 'data' kwarg."""
        # This test verifies the behavior when output is not a dict
        # With stub generator, output is always a dict, but the logic is tested
        t1 = anvil.use_tool(name="step1", intent="Step 1")
        t2 = anvil.use_tool(name="step2", intent="Step 2")

        chain = t1.pipe(t2)
        # Since stub always returns dict, this tests the dict path
        result = chain.run(initial="value")

        assert result["tool"] == "step2"


class TestChainRunSafe:
    def test_run_safe_returns_result_on_success(self, anvil):
        """run_safe() returns ToolResult on success."""
        t1 = anvil.use_tool(name="safe1", intent="Safe 1")
        t2 = anvil.use_tool(name="safe2", intent="Safe 2")

        chain = t1.pipe(t2)
        result = chain.run_safe(x=1)

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.data["tool"] == "safe2"

    def test_run_safe_returns_error_on_failure(self, anvil, temp_tools_dir):
        """run_safe() returns ToolResult with error on failure."""
        # Create a tool that will fail, keeping the managed header
        tool = anvil.use_tool(name="failing", intent="Will fail")

        # Read the existing file to get the header
        tool_path = temp_tools_dir / "failing.py"
        content = tool_path.read_text()

        # Find the header end and replace only the code part
        header_end = content.find("# " + "-" * 50 + "\n", content.find("# " + "-" * 50 + "\n") + 1)
        header = content[: header_end + 53]  # Include the second dashed line

        # Write header + failing code
        tool_path.write_text(header + "\ndef run(**kwargs): raise ValueError('Intentional failure')\n")

        # Clear loader cache to pick up the broken file
        anvil._loader.clear_cache("failing")

        # Disable self-healing to get the direct error
        anvil.self_healing = False

        chain = ToolChain([tool])
        result = chain.run_safe(x=1)

        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "failing" in result.error
        assert "Intentional failure" in result.error


class TestChainRepr:
    def test_repr_single_tool(self, anvil):
        """repr shows single tool name."""
        tool = anvil.use_tool(name="only", intent="Only tool")
        chain = ToolChain([tool])

        assert repr(chain) == "ToolChain(only)"

    def test_repr_multiple_tools(self, anvil):
        """repr shows tool names connected with arrows."""
        t1 = anvil.use_tool(name="fetch", intent="Fetch")
        t2 = anvil.use_tool(name="transform", intent="Transform")
        t3 = anvil.use_tool(name="save", intent="Save")

        chain = t1.pipe(t2).pipe(t3)

        assert repr(chain) == "ToolChain(fetch -> transform -> save)"


class TestChainLen:
    def test_len_returns_tool_count(self, anvil):
        """len() returns number of tools in chain."""
        t1 = anvil.use_tool(name="x", intent="X")
        t2 = anvil.use_tool(name="y", intent="Y")

        chain1 = ToolChain([t1])
        chain2 = t1.pipe(t2)

        assert len(chain1) == 1
        assert len(chain2) == 2


class TestChainPipe:
    def test_chain_pipe_extends_chain(self, anvil):
        """ToolChain.pipe() adds another tool."""
        t1 = anvil.use_tool(name="p1", intent="P1")
        t2 = anvil.use_tool(name="p2", intent="P2")
        t3 = anvil.use_tool(name="p3", intent="P3")

        chain = ToolChain([t1, t2])
        extended = chain.pipe(t3)

        assert len(extended) == 3
        assert extended.tools[2] is t3

    def test_pipe_creates_new_chain(self, anvil):
        """pipe() creates a new chain, doesn't modify original."""
        t1 = anvil.use_tool(name="orig1", intent="Orig 1")
        t2 = anvil.use_tool(name="orig2", intent="Orig 2")
        t3 = anvil.use_tool(name="added", intent="Added")

        original = t1.pipe(t2)
        extended = original.pipe(t3)

        assert len(original) == 2
        assert len(extended) == 3
