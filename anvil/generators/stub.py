"""Stub Generator - Testing mode.

This generator returns mock tool code for testing
without requiring any API keys or network access.
"""

from typing import Any

from anvil.generators.base import BaseGenerator, GeneratorMode
from anvil.models import GeneratedCode, ToolConfig


class StubGenerator(BaseGenerator):
    """Stub generator for testing without real API calls.

    Use this when:
    - Running tests
    - Developing locally without API keys
    - Demonstrating SDK functionality

    Example:
        ```python
        # For testing
        generator = StubGenerator()
        code = generator.generate(config)

        # In Anvil
        anvil = Anvil(use_stub=True)
        ```
    """

    def __init__(self, **kwargs: Any):
        """Initialize the stub generator.

        Args:
            **kwargs: Ignored, for API compatibility
        """
        pass

    @property
    def mode(self) -> GeneratorMode:
        """Return the generator mode."""
        return GeneratorMode.STUB

    def fetch_documentation(self, docs_url: str | None) -> str:
        """Return stub documentation."""
        return f"Stub documentation for: {docs_url or 'no URL'}"

    def generate(self, config: ToolConfig) -> GeneratedCode:
        """Generate stub code for testing."""
        escaped_intent = config.intent.replace('"', '\\"')

        code = f'''"""Auto-generated tool: {config.name}

Intent: {escaped_intent}
Docs: {config.docs_url or 'None'}
"""

import os


def run(**kwargs):
    """Execute the tool.

    This is a stub implementation for testing.

    Args:
        **kwargs: Tool-specific arguments

    Returns:
        dict: Result of the tool execution
    """
    return {{
        "tool": "{config.name}",
        "intent": "{escaped_intent}",
        "args": kwargs,
        "status": "stub_execution",
        "message": "This is a stub. Real implementation pending.",
    }}
'''
        return GeneratedCode(code=code, dependencies=[])

    def generate_fix(
        self,
        config: ToolConfig,
        previous_code: str,
        error_message: str,
    ) -> GeneratedCode:
        """Return stub fixed code."""
        return self.generate(config)
