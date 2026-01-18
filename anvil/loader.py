"""Dynamic tool loader - loads tool modules at runtime using importlib."""

import importlib.util
import sys
from pathlib import Path
from typing import Any, Callable

from anvil.models import ToolResult


class ToolLoader:
    """Dynamically loads and executes tool modules."""

    def __init__(self, tools_dir: Path):
        self.tools_dir = tools_dir
        self._cache: dict[str, Any] = {}

    def load_module(self, name: str, force_reload: bool = False) -> Any:
        """Load a tool module by name.

        Args:
            name: The tool name (without .py extension)
            force_reload: If True, reload even if cached

        Returns:
            The loaded module object

        Raises:
            FileNotFoundError: If the tool file doesn't exist
            ImportError: If the module fails to load
        """
        if name in self._cache and not force_reload:
            return self._cache[name]

        path = self.tools_dir / f"{name}.py"
        if not path.exists():
            raise FileNotFoundError(f"Tool not found: {path}")

        # Create a unique module name to avoid conflicts
        module_name = f"anvil_tools.{name}"

        # Remove from sys.modules if reloading
        if force_reload and module_name in sys.modules:
            del sys.modules[module_name]

        # Load the module from file
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Failed to create spec for {path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        self._cache[name] = module
        return module

    def get_run_function(self, name: str) -> Callable[..., Any]:
        """Get the `run` function from a tool module.

        Args:
            name: The tool name

        Returns:
            The run() function from the module

        Raises:
            AttributeError: If the module has no run() function
        """
        module = self.load_module(name)

        if not hasattr(module, "run"):
            raise AttributeError(f"Tool '{name}' has no run() function")

        return module.run  # type: ignore[no-any-return]

    def execute(self, tool_name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool's run() function and wrap the result.

        Args:
            tool_name: The tool name
            **kwargs: Arguments to pass to the run() function

        Returns:
            ToolResult with success/error status
        """
        try:
            run_fn = self.get_run_function(tool_name)
            result = run_fn(**kwargs)
            return ToolResult(success=True, data=result)
        except FileNotFoundError as e:
            return ToolResult(success=False, error=f"Tool not found: {e}")
        except AttributeError as e:
            return ToolResult(success=False, error=f"Invalid tool: {e}")
        except Exception as e:
            return ToolResult(success=False, error=f"Execution failed: {e}")

    def clear_cache(self, name: str | None = None) -> None:
        """Clear the module cache.

        Args:
            name: If provided, only clear this tool. Otherwise clear all.
        """
        if name is not None:
            self._cache.pop(name, None)
            module_name = f"anvil_tools.{name}"
            sys.modules.pop(module_name, None)
        else:
            for cached_name in list(self._cache.keys()):
                module_name = f"anvil_tools.{cached_name}"
                sys.modules.pop(module_name, None)
            self._cache.clear()
