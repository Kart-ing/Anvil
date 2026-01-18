"""JIT Generator - generates tool code from intent and documentation.

This module provides backward-compatible imports for the refactored
generator architecture. The actual implementations are now in:

- anvil.generators.local.LocalGenerator (BYO API Keys)
- anvil.generators.stub.StubGenerator (Testing)

For Anvil Cloud integration, install anvil-cloud:
    pip install anvil-cloud

For new code, prefer importing from anvil.generators directly.
"""

# Re-export from new architecture for backward compatibility
from anvil.generators.base import BaseGenerator, GeneratorMode
from anvil.generators.local import LocalGenerator, _extract_code
from anvil.generators.stub import StubGenerator

# Backward compatible aliases - these are what existing code imports
JITGenerator = LocalGenerator
StubJITGenerator = StubGenerator


def get_generator(
    mode: str = "local",
    api_key: str | None = None,
    firecrawl_key: str | None = None,
    model: str | None = None,
    provider: str = "anthropic",
) -> BaseGenerator:
    """Factory function to get the appropriate generator.

    Args:
        mode: Generator mode ('local', 'stub')
        api_key: LLM API key for local mode
        firecrawl_key: FireCrawl API key for documentation
        model: Model to use for generation
        provider: LLM provider ('anthropic', 'openai', 'grok')

    Returns:
        Configured generator instance

    Example:
        ```python
        # Local mode (BYO keys)
        gen = get_generator(mode="local", provider="openai")

        # Testing
        gen = get_generator(mode="stub")
        ```

    Note:
        For Anvil Cloud mode, install anvil-cloud package:
            pip install anvil-cloud
    """
    mode = mode.lower()

    if mode == "stub":
        return StubGenerator()

    if mode == "cloud":
        # Try to import from anvil-cloud package
        try:
            from anvil_cloud import CloudGenerator

            return CloudGenerator(api_key=api_key)
        except ImportError:
            raise ImportError(
                "Anvil Cloud mode requires the anvil-cloud package. "
                "Install it with: pip install anvil-cloud"
            )

    # Default to local
    return LocalGenerator(
        api_key=api_key,
        firecrawl_key=firecrawl_key,
        model=model,
        provider=provider,
    )


__all__ = [
    # New architecture
    "BaseGenerator",
    "GeneratorMode",
    "LocalGenerator",
    "StubGenerator",
    "get_generator",
    # Backward compatibility
    "JITGenerator",
    "StubJITGenerator",
    "_extract_code",
]
