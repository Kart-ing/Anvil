"""AutoGen adapter for Anvil tools.

Converts Anvil tools to AutoGen FunctionTool instances that can be used
with AutoGen agents.
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
    model_name = f"{tool.name.title().replace('_', '')}Args"
    return create_model(model_name, **fields)


def to_autogen_tool(tool: "Tool") -> Any:
    """Convert an Anvil tool to an AutoGen FunctionTool.

    This creates an AutoGen-compatible tool that wraps the Anvil tool's
    run() method. The tool can then be used with AutoGen agents.

    Args:
        tool: Anvil Tool instance

    Returns:
        AutoGen FunctionTool instance

    Raises:
        ImportError: If autogen-core is not installed

    Example:
        ```python
        from anvil import Anvil

        anvil = Anvil()
        search = anvil.use_tool(name="search", intent="Search the web")

        # Convert to AutoGen tool
        autogen_tool = search.to_autogen()

        # Use with AutoGen agent
        from autogen_agentchat.agents import AssistantAgent
        agent = AssistantAgent(
            name="assistant",
            tools=[autogen_tool]
        )
        ```
    """
    try:
        from autogen_core.tools import FunctionTool
    except ImportError:
        raise ImportError(
            "autogen-core is required for AutoGen integration. "
            "Install with: pip install autogen-core"
        )

    # Capture tool reference for closure
    anvil_tool = tool

    # Create the wrapper function
    def tool_func(**kwargs: Any) -> Any:
        """Execute the Anvil tool."""
        return anvil_tool.run(**kwargs)

    # Set function metadata
    tool_func.__name__ = anvil_tool.name
    tool_func.__doc__ = anvil_tool.config.intent

    # Create the FunctionTool
    return FunctionTool(
        func=tool_func,
        name=anvil_tool.name,
        description=anvil_tool.config.intent,
    )


def to_autogen_base_tool(tool: "Tool") -> Any:
    """Convert an Anvil tool to an AutoGen BaseTool subclass.

    This is an alternative that creates a class-based tool with
    explicit args_type for stronger typing.

    Args:
        tool: Anvil Tool instance

    Returns:
        AutoGen BaseTool instance

    Raises:
        ImportError: If autogen-core is not installed
    """
    try:
        from autogen_core import CancellationToken
        from autogen_core.tools import BaseTool
    except ImportError:
        raise ImportError(
            "autogen-core is required for AutoGen integration. "
            "Install with: pip install autogen-core"
        )

    # Capture tool reference
    anvil_tool = tool

    # Create args schema if tool has inputs
    if tool.config.inputs:
        args_type = _create_pydantic_model(tool)
    else:
        # Empty args model
        from pydantic import BaseModel

        class EmptyArgs(BaseModel):
            pass

        args_type = EmptyArgs

    # Define the tool class
    class AnvilAutoGenTool(BaseTool[args_type, Any]):  # type: ignore[valid-type]
        """AutoGen tool wrapping an Anvil tool."""

        def __init__(self) -> None:
            super().__init__(
                args_type=args_type,
                return_type=Any,
                name=anvil_tool.name,
                description=anvil_tool.config.intent,
            )

        async def run(self, args: args_type, cancellation_token: CancellationToken) -> Any:  # type: ignore[valid-type]
            """Execute the Anvil tool."""
            # Convert Pydantic model to dict for Anvil
            kwargs = args.model_dump() if hasattr(args, "model_dump") else dict(args)
            return anvil_tool.run(**kwargs)

    return AnvilAutoGenTool()
