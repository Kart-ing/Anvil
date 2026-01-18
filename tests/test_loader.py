"""Tests for dynamic tool loader."""

import tempfile
from pathlib import Path

import pytest

from anvil.loader import ToolLoader


@pytest.fixture
def temp_tools_dir():
    """Create a temporary directory for tool files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_dir = Path(tmpdir) / "anvil_tools"
        tools_dir.mkdir()
        yield tools_dir


@pytest.fixture
def loader(temp_tools_dir):
    """Create a ToolLoader with temporary directory."""
    return ToolLoader(tools_dir=temp_tools_dir)


def write_tool(tools_dir: Path, name: str, code: str) -> Path:
    """Helper to write a tool file."""
    path = tools_dir / f"{name}.py"
    path.write_text(code)
    return path


class TestLoadModule:
    def test_load_simple_module(self, loader, temp_tools_dir):
        """Can load a simple module."""
        write_tool(temp_tools_dir, "simple", "VALUE = 42\ndef run(): return VALUE")

        module = loader.load_module("simple")

        assert module.VALUE == 42
        assert module.run() == 42

    def test_load_missing_module(self, loader):
        """Raises FileNotFoundError for missing tool."""
        with pytest.raises(FileNotFoundError):
            loader.load_module("nonexistent")

    def test_caches_module(self, loader, temp_tools_dir):
        """Module is cached after first load."""
        write_tool(temp_tools_dir, "cached", "VALUE = 1\ndef run(): return VALUE")

        module1 = loader.load_module("cached")
        module2 = loader.load_module("cached")

        assert module1 is module2

    def test_force_reload(self, loader, temp_tools_dir):
        """force_reload bypasses cache."""
        path = write_tool(temp_tools_dir, "reloadable", "VALUE = 1\ndef run(): return VALUE")

        module1 = loader.load_module("reloadable")
        assert module1.VALUE == 1

        # Modify the file
        path.write_text("VALUE = 999\ndef run(): return VALUE")

        # Without force_reload, still get cached version
        module2 = loader.load_module("reloadable")
        assert module2.VALUE == 1

        # With force_reload, get updated version
        module3 = loader.load_module("reloadable", force_reload=True)
        assert module3.VALUE == 999


class TestGetRunFunction:
    def test_get_run_function(self, loader, temp_tools_dir):
        """Can get run function from module."""
        write_tool(temp_tools_dir, "runnable", "def run(x): return x * 2")

        run_fn = loader.get_run_function("runnable")
        assert run_fn(5) == 10

    def test_missing_run_function(self, loader, temp_tools_dir):
        """Raises AttributeError if no run() function."""
        write_tool(temp_tools_dir, "no_run", "VALUE = 42")

        with pytest.raises(AttributeError, match="no run"):
            loader.get_run_function("no_run")


class TestExecute:
    def test_execute_success(self, loader, temp_tools_dir):
        """Execute returns success result."""
        write_tool(temp_tools_dir, "greet", "def run(name='World'): return f'Hello, {name}!'")

        result = loader.execute("greet", name="Anvil")

        assert result.success is True
        assert result.data == "Hello, Anvil!"
        assert result.error is None

    def test_execute_with_defaults(self, loader, temp_tools_dir):
        """Execute uses default arguments."""
        write_tool(temp_tools_dir, "greet", "def run(name='World'): return f'Hello, {name}!'")

        result = loader.execute("greet")

        assert result.success is True
        assert result.data == "Hello, World!"

    def test_execute_missing_tool(self, loader):
        """Execute returns error for missing tool."""
        result = loader.execute("missing")

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_execute_no_run_function(self, loader, temp_tools_dir):
        """Execute returns error for tool without run()."""
        write_tool(temp_tools_dir, "broken", "VALUE = 42")

        result = loader.execute("broken")

        assert result.success is False
        assert "no run" in result.error.lower()

    def test_execute_runtime_error(self, loader, temp_tools_dir):
        """Execute catches runtime errors."""
        write_tool(temp_tools_dir, "error", "def run(): raise ValueError('oops')")

        result = loader.execute("error")

        assert result.success is False
        assert "oops" in result.error


class TestClearCache:
    def test_clear_single_tool(self, loader, temp_tools_dir):
        """Can clear cache for a single tool."""
        write_tool(temp_tools_dir, "tool1", "VALUE = 1\ndef run(): return VALUE")
        write_tool(temp_tools_dir, "tool2", "VALUE = 2\ndef run(): return VALUE")

        loader.load_module("tool1")
        loader.load_module("tool2")
        assert "tool1" in loader._cache
        assert "tool2" in loader._cache

        loader.clear_cache("tool1")

        assert "tool1" not in loader._cache
        assert "tool2" in loader._cache

    def test_clear_all(self, loader, temp_tools_dir):
        """Can clear entire cache."""
        write_tool(temp_tools_dir, "tool1", "VALUE = 1\ndef run(): return VALUE")
        write_tool(temp_tools_dir, "tool2", "VALUE = 2\ndef run(): return VALUE")

        loader.load_module("tool1")
        loader.load_module("tool2")

        loader.clear_cache()

        assert len(loader._cache) == 0
