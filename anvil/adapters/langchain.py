"""LangChain adapter for Anvil tools.

Converts Anvil tools to LangChain BaseTool instances that can be used
with LangChain agents and chains.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from anvil.core import Tool


def _create_pydantic_model(tool: "Tool") -> type:
    """Dynamically create a Pydantic model from InputParam list.

    Args:
        tool: Anvil Tool instance

    Returns:
        Pydantic BaseModel class for the tool's inputs
    """
    from pydantic import BaseModel, Field, create_model

    fields: dict[str, Any] = {}

    for param in tool.config.inputs:
        # Map Anvil types to Python types
        type_map = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
        }
        python_type = type_map.get(param.param_type, str)

        # Build field with description and default
        if param.required:
            if param.default is not None:
                fields[param.name] = (
                    python_type,
                    Field(default=param.default, description=param.description or ""),
                )
            else:
                fields[param.name] = (
                    python_type,
                    Field(..., description=param.description or ""),
                )
        else:
            fields[param.name] = (
                python_type | None,
                Field(default=param.default, description=param.description or ""),
            )

    # Create the model dynamically
    model_name = f"{tool.name.title().replace('_', '')}Input"
    return create_model(model_name, **fields)


def to_langchain_tool(tool: "Tool") -> Any:
    """Convert an Anvil tool to a LangChain BaseTool.

    This creates a LangChain-compatible tool that wraps the Anvil tool's
    run() method. The tool can then be used with LangChain agents.

    Args:
        tool: Anvil Tool instance

    Returns:
        LangChain BaseTool instance

    Raises:
        ImportError: If langchain-core is not installed

    Example:
        ```python
        from anvil import Anvil

        anvil = Anvil()
        search = anvil.use_tool(name="search", intent="Search the web")

        # Convert to LangChain tool
        lc_tool = search.to_langchain()

        # Use with LangChain agent
        from langchain.agents import create_react_agent
        agent = create_react_agent(llm, [lc_tool])
        ```
    """
    try:
        from langchain_core.tools import BaseTool
    except ImportError:
        raise ImportError(
            "langchain-core is required for LangChain integration. "
            "Install with: pip install langchain-core"
        )

    # Create args schema from InputParam
    args_schema = None
    if tool.config.inputs:
        args_schema = _create_pydantic_model(tool)

    # Capture tool reference for closure
    anvil_tool = tool

    class AnvilLangChainTool(BaseTool):
        """LangChain tool wrapping an Anvil tool."""

        name: str = anvil_tool.name
        description: str = anvil_tool.config.intent

        def __init__(self, **kwargs: Any):
            super().__init__(**kwargs)
            if args_schema is not None:
                self.args_schema = args_schema

        def _run(self, **kwargs: Any) -> Any:
            """Execute the Anvil tool."""
            return anvil_tool.run(**kwargs)

        async def _arun(self, **kwargs: Any) -> Any:
            """Execute the Anvil tool asynchronously."""
            return await anvil_tool.run_async(**kwargs)

    return AnvilLangChainTool()


def to_langchain_structured_tool(tool: "Tool") -> Any:
    """Convert an Anvil tool to a LangChain StructuredTool.

    Alternative to BaseTool that uses StructuredTool.from_function().

    Args:
        tool: Anvil Tool instance

    Returns:
        LangChain StructuredTool instance
    """
    try:
        from langchain_core.tools import StructuredTool
    except ImportError:
        raise ImportError(
            "langchain-core is required for LangChain integration. "
            "Install with: pip install langchain-core"
        )

    # Create args schema if inputs defined
    args_schema = None
    if tool.config.inputs:
        args_schema = _create_pydantic_model(tool)

    return StructuredTool.from_function(
        func=tool.run,
        coroutine=tool.run_async,
        name=tool.name,
        description=tool.config.intent,
        args_schema=args_schema,
    )
