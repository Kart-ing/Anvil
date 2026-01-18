"""CrewAI adapter for Anvil tools.

Converts Anvil tools to CrewAI Tool instances that can be used
with CrewAI agents and crews.
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


def to_crewai_tool(tool: "Tool") -> Any:
    """Convert an Anvil tool to a CrewAI Tool.

    This creates a CrewAI-compatible tool that wraps the Anvil tool's
    run() method. The tool can then be used with CrewAI agents.

    Args:
        tool: Anvil Tool instance

    Returns:
        CrewAI BaseTool instance

    Raises:
        ImportError: If crewai is not installed

    Example:
        ```python
        from anvil import Anvil

        anvil = Anvil()
        search = anvil.use_tool(name="search", intent="Search the web")

        # Convert to CrewAI tool
        crew_tool = search.to_crewai()

        # Use with CrewAI agent
        from crewai import Agent
        agent = Agent(
            role="Researcher",
            tools=[crew_tool]
        )
        ```
    """
    try:
        from crewai.tools import BaseTool as CrewAIBaseTool
    except ImportError:
        raise ImportError(
            "crewai is required for CrewAI integration. "
            "Install with: pip install crewai"
        )

    # Capture tool reference for closure
    anvil_tool = tool
    tool_name = anvil_tool.name
    tool_description = anvil_tool.config.intent

    # Create args_schema if tool has inputs
    args_schema_class = None
    if tool.config.inputs:
        args_schema_class = _create_pydantic_model(tool)

    # Define the class with proper type annotations
    if args_schema_class is not None:
        class AnvilCrewAITool(CrewAIBaseTool):
            """CrewAI tool wrapping an Anvil tool."""

            name: str = tool_name
            description: str = tool_description
            args_schema: type = args_schema_class

            def _run(self, **kwargs: Any) -> Any:
                """Execute the Anvil tool."""
                return anvil_tool.run(**kwargs)
    else:
        class AnvilCrewAITool(CrewAIBaseTool):  # type: ignore[no-redef]
            """CrewAI tool wrapping an Anvil tool."""

            name: str = tool_name
            description: str = tool_description

            def _run(self, **kwargs: Any) -> Any:
                """Execute the Anvil tool."""
                return anvil_tool.run(**kwargs)

    return AnvilCrewAITool()


def to_crewai_function_tool(tool: "Tool") -> Any:
    """Convert an Anvil tool to a CrewAI tool using the @tool decorator approach.

    This is an alternative that creates a function-based tool.

    Args:
        tool: Anvil Tool instance

    Returns:
        CrewAI tool instance
    """
    try:
        from crewai.tools import tool as crewai_tool_decorator
    except ImportError:
        raise ImportError(
            "crewai is required for CrewAI integration. "
            "Install with: pip install crewai"
        )

    # Create a wrapper function with proper docstring
    def tool_func(**kwargs: Any) -> Any:
        return tool.run(**kwargs)

    # Set function metadata
    tool_func.__name__ = tool.name
    tool_func.__doc__ = tool.config.intent

    # Apply the decorator
    return crewai_tool_decorator(tool.name)(tool_func)
