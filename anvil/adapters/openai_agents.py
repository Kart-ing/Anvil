"""OpenAI Agents SDK adapter for Anvil tools.

Converts Anvil tools to OpenAI Agents SDK function tools that can be used
with OpenAI Agents.
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
    model_name = f"{tool.name.title().replace('_', '')}Params"
    return create_model(model_name, **fields)


def to_openai_agents_tool(tool: "Tool") -> Any:
    """Convert an Anvil tool to an OpenAI Agents SDK function tool.

    This creates an OpenAI Agents SDK-compatible tool that wraps the Anvil
    tool's run() method. The tool can then be used with OpenAI Agents.

    Args:
        tool: Anvil Tool instance

    Returns:
        OpenAI Agents SDK FunctionTool instance

    Raises:
        ImportError: If openai-agents is not installed

    Example:
        ```python
        from anvil import Anvil

        anvil = Anvil()
        search = anvil.use_tool(name="search", intent="Search the web")

        # Convert to OpenAI Agents tool
        oai_tool = search.to_openai_agents()

        # Use with OpenAI Agent
        from agents import Agent
        agent = Agent(
            name="assistant",
            tools=[oai_tool]
        )
        ```
    """
    try:
        from agents import FunctionTool
    except ImportError:
        raise ImportError(
            "openai-agents is required for OpenAI Agents SDK integration. "
            "Install with: pip install openai-agents"
        )

    # Capture tool reference
    anvil_tool = tool

    # Create the invocation handler
    async def on_invoke(ctx: Any, args: str) -> Any:
        """Handle tool invocation."""
        import json

        # Parse the JSON args
        kwargs = json.loads(args) if args else {}
        return anvil_tool.run(**kwargs)

    # Build JSON schema from inputs
    json_schema = _build_json_schema(tool)

    # Create the FunctionTool with strict=False to allow flexibility
    return FunctionTool(
        name=anvil_tool.name,
        description=anvil_tool.config.intent,
        params_json_schema=json_schema,
        on_invoke_tool=on_invoke,
        strict_json_schema=False,
    )


def to_openai_agents_tool_class(tool: "Tool") -> Any:
    """Convert an Anvil tool to an OpenAI Agents SDK FunctionTool class.

    This is an alternative approach using the FunctionTool class directly
    for more control over the tool definition.

    Args:
        tool: Anvil Tool instance

    Returns:
        OpenAI Agents SDK FunctionTool instance

    Raises:
        ImportError: If openai-agents is not installed
    """
    try:
        from agents import FunctionTool, RunContextWrapper
    except ImportError:
        raise ImportError(
            "openai-agents is required for OpenAI Agents SDK integration. "
            "Install with: pip install openai-agents"
        )

    # Capture tool reference
    anvil_tool = tool

    # Create the invocation handler
    async def on_invoke(ctx: RunContextWrapper[Any], args: str) -> Any:
        """Handle tool invocation."""
        import json

        # Parse the JSON args
        kwargs = json.loads(args) if args else {}
        return anvil_tool.run(**kwargs)

    # Build JSON schema from inputs
    json_schema = _build_json_schema(tool)

    # Create the FunctionTool
    return FunctionTool(
        name=anvil_tool.name,
        description=anvil_tool.config.intent,
        params_json_schema=json_schema,
        on_invoke_tool=on_invoke,
    )


def _build_json_schema(tool: "Tool") -> dict[str, Any]:
    """Build JSON schema from tool inputs.

    Args:
        tool: Anvil Tool instance

    Returns:
        JSON schema dict for the tool's parameters
    """
    properties: dict[str, Any] = {}
    required: list[str] = []

    type_map = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
    }

    for param in tool.config.inputs:
        json_type = type_map.get(param.param_type, "string")

        prop: dict[str, Any] = {"type": json_type}
        if param.description:
            prop["description"] = param.description
        if param.default is not None:
            prop["default"] = param.default

        properties[param.name] = prop

        if param.required:
            required.append(param.name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }

    if required:
        schema["required"] = required

    return schema
