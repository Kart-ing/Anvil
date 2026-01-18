"""Tool chaining - pipe tool outputs to inputs."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from anvil.models import ToolResult

if TYPE_CHECKING:
    from anvil.core import Tool


class ToolChain:
    """A chain of tools that execute sequentially.

    The output of each tool becomes the input to the next tool.
    Supports fluent API via pipe().

    Example:
        chain = tool1.pipe(tool2).pipe(tool3)
        result = chain.run(initial_data="...")

        # Or build manually
        chain = ToolChain([tool1, tool2, tool3])
        result = chain.run(x=1, y=2)
    """

    def __init__(self, tools: list[Tool]):
        """Initialize the chain with a list of tools.

        Args:
            tools: Ordered list of tools to execute
        """
        if not tools:
            raise ValueError("ToolChain requires at least one tool")
        self.tools = tools

    def pipe(self, tool: Tool) -> ToolChain:
        """Add another tool to the chain.

        Args:
            tool: Tool to add at the end of the chain

        Returns:
            New ToolChain with the added tool
        """
        return ToolChain(self.tools + [tool])

    def run(self, **initial_kwargs: Any) -> Any:
        """Execute the chain with initial arguments.

        Each tool's output is passed as input to the next tool.
        If a tool returns a dict, it's unpacked as kwargs.
        Otherwise, it's passed as a 'data' kwarg.

        Args:
            **initial_kwargs: Initial arguments for the first tool

        Returns:
            The final tool's output

        Raises:
            RuntimeError: If any tool in the chain fails
        """
        result: Any = initial_kwargs

        for i, tool in enumerate(self.tools):
            try:
                if isinstance(result, dict):
                    # Unpack dict as kwargs
                    result = tool.run(**result)
                else:
                    # Pass as 'data' kwarg
                    result = tool.run(data=result)
            except Exception as e:
                raise RuntimeError(
                    f"Chain failed at tool '{tool.name}' (step {i + 1}/{len(self.tools)}): {e}"
                ) from e

        return result

    def run_safe(self, **initial_kwargs: Any) -> ToolResult:
        """Execute the chain and return a ToolResult (no exceptions).

        Args:
            **initial_kwargs: Initial arguments for the first tool

        Returns:
            ToolResult with success status and data/error
        """
        try:
            result = self.run(**initial_kwargs)
            return ToolResult(success=True, data=result)
        except RuntimeError as e:
            return ToolResult(success=False, error=str(e))

    async def run_async(self, **initial_kwargs: Any) -> Any:
        """Execute the chain asynchronously.

        Each tool's output is passed as input to the next tool.
        Runs in a thread pool executor to avoid blocking.

        Args:
            **initial_kwargs: Initial arguments for the first tool

        Returns:
            The final tool's output

        Raises:
            RuntimeError: If any tool in the chain fails
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.run(**initial_kwargs))

    async def run_safe_async(self, **initial_kwargs: Any) -> ToolResult:
        """Execute the chain asynchronously and return a ToolResult (no exceptions).

        Args:
            **initial_kwargs: Initial arguments for the first tool

        Returns:
            ToolResult with success status and data/error
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.run_safe(**initial_kwargs))

    def __len__(self) -> int:
        """Return the number of tools in the chain."""
        return len(self.tools)

    def __repr__(self) -> str:
        """Return string representation of the chain."""
        tool_names = " -> ".join(t.name for t in self.tools)
        return f"ToolChain({tool_names})"
