"""Tests for async tool execution."""

import asyncio
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


class TestToolRunAsync:
    @pytest.mark.asyncio
    async def test_run_async_executes_tool(self, anvil):
        """run_async() executes the tool asynchronously."""
        tool = anvil.use_tool(name="async_tool", intent="Async test")

        result = await tool.run_async(query="test")

        assert isinstance(result, dict)
        assert result["tool"] == "async_tool"
        assert result["args"] == {"query": "test"}

    @pytest.mark.asyncio
    async def test_run_async_with_multiple_args(self, anvil):
        """run_async() passes all kwargs."""
        tool = anvil.use_tool(name="multi_async", intent="Multiple args")

        result = await tool.run_async(a=1, b="two", c=True)

        assert result["args"] == {"a": 1, "b": "two", "c": True}

    @pytest.mark.asyncio
    async def test_run_async_parallel_execution(self, anvil):
        """Multiple tools can run in parallel with asyncio.gather."""
        tool1 = anvil.use_tool(name="parallel1", intent="Parallel 1")
        tool2 = anvil.use_tool(name="parallel2", intent="Parallel 2")
        tool3 = anvil.use_tool(name="parallel3", intent="Parallel 3")

        results = await asyncio.gather(
            tool1.run_async(x=1),
            tool2.run_async(x=2),
            tool3.run_async(x=3),
        )

        assert len(results) == 3
        assert results[0]["tool"] == "parallel1"
        assert results[1]["tool"] == "parallel2"
        assert results[2]["tool"] == "parallel3"

    @pytest.mark.asyncio
    async def test_run_async_raises_on_failure(self, anvil, temp_tools_dir):
        """run_async() raises RuntimeError on failure."""
        tool = anvil.use_tool(name="fail_async", intent="Will fail")

        # Break the tool file (without header - treated as ejected)
        tool_path = temp_tools_dir / "fail_async.py"
        tool_path.write_text("def run(**kwargs): raise ValueError('Async failure')")

        anvil._loader.clear_cache("fail_async")
        anvil.self_healing = False

        with pytest.raises(RuntimeError) as exc_info:
            await tool.run_async(x=1)

        assert "Async failure" in str(exc_info.value)


class TestToolRunSafeAsync:
    @pytest.mark.asyncio
    async def test_run_safe_async_returns_result(self, anvil):
        """run_safe_async() returns ToolResult on success."""
        tool = anvil.use_tool(name="safe_async", intent="Safe async")

        result = await tool.run_safe_async(data="test")

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.data["tool"] == "safe_async"

    @pytest.mark.asyncio
    async def test_run_safe_async_returns_error_on_failure(self, anvil, temp_tools_dir):
        """run_safe_async() returns ToolResult with error on failure."""
        tool = anvil.use_tool(name="error_async", intent="Error async")

        # Break the tool file
        tool_path = temp_tools_dir / "error_async.py"
        tool_path.write_text("def run(**kwargs): raise ValueError('Safe async error')")

        anvil._loader.clear_cache("error_async")
        anvil.self_healing = False

        result = await tool.run_safe_async(x=1)

        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "Safe async error" in result.error


class TestChainRunAsync:
    @pytest.mark.asyncio
    async def test_chain_run_async(self, anvil):
        """ToolChain.run_async() executes chain asynchronously."""
        t1 = anvil.use_tool(name="chain_async1", intent="Chain 1")
        t2 = anvil.use_tool(name="chain_async2", intent="Chain 2")

        chain = t1.pipe(t2)
        result = await chain.run_async(input="start")

        assert result["tool"] == "chain_async2"

    @pytest.mark.asyncio
    async def test_chain_run_async_multiple_chains(self, anvil):
        """Multiple chains can run in parallel."""
        t1 = anvil.use_tool(name="mc1", intent="MC 1")
        t2 = anvil.use_tool(name="mc2", intent="MC 2")
        t3 = anvil.use_tool(name="mc3", intent="MC 3")
        t4 = anvil.use_tool(name="mc4", intent="MC 4")

        chain1 = t1.pipe(t2)
        chain2 = t3.pipe(t4)

        results = await asyncio.gather(
            chain1.run_async(a=1),
            chain2.run_async(b=2),
        )

        assert len(results) == 2
        assert results[0]["tool"] == "mc2"
        assert results[1]["tool"] == "mc4"


class TestChainRunSafeAsync:
    @pytest.mark.asyncio
    async def test_chain_run_safe_async_success(self, anvil):
        """ToolChain.run_safe_async() returns ToolResult on success."""
        t1 = anvil.use_tool(name="csa1", intent="CSA 1")
        t2 = anvil.use_tool(name="csa2", intent="CSA 2")

        chain = t1.pipe(t2)
        result = await chain.run_safe_async(x=1)

        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.data["tool"] == "csa2"

    @pytest.mark.asyncio
    async def test_chain_run_safe_async_failure(self, anvil, temp_tools_dir):
        """ToolChain.run_safe_async() returns ToolResult with error on failure."""
        t1 = anvil.use_tool(name="csaf1", intent="CSAF 1")
        t2 = anvil.use_tool(name="csaf2", intent="CSAF 2")

        # Break second tool
        tool_path = temp_tools_dir / "csaf2.py"
        tool_path.write_text("def run(**kwargs): raise ValueError('Chain async fail')")

        anvil._loader.clear_cache("csaf2")
        anvil.self_healing = False

        chain = t1.pipe(t2)
        result = await chain.run_safe_async(x=1)

        assert isinstance(result, ToolResult)
        assert result.success is False
        assert "csaf2" in result.error


class TestAsyncWithSelfHealing:
    @pytest.mark.asyncio
    async def test_async_triggers_self_healing(self, anvil, temp_tools_dir):
        """run_async() triggers self-healing on failure."""
        tool = anvil.use_tool(name="heal_async", intent="Self-healing async")

        # Read original content to get header
        tool_path = temp_tools_dir / "heal_async.py"
        original = tool_path.read_text()

        # Find header end
        dash_line = "# " + "-" * 50
        first_dash = original.find(dash_line)
        second_dash = original.find(dash_line, first_dash + 1)
        header = original[: second_dash + len(dash_line) + 1]

        # Write broken code with header (so it's still managed)
        tool_path.write_text(header + "\ndef run(**kwargs): raise ValueError('Need healing')\n")

        anvil._loader.clear_cache("heal_async")

        # With self-healing enabled (default), it should attempt to heal
        # The stub generator will regenerate working code
        result = await tool.run_async(x=1)

        # After healing, should work
        assert result["tool"] == "heal_async"
