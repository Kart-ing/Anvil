"""Tool generators for Anvil.

This module provides different generator backends:
- LocalGenerator: Uses your own LLM API keys (BYO Keys mode)
- StubGenerator: For testing without API keys

For Anvil Cloud integration (instant cached tools), install anvil-cloud:
    pip install anvil-cloud
"""

from anvil.generators.base import BaseGenerator, GeneratorMode
from anvil.generators.local import LocalGenerator
from anvil.generators.stub import StubGenerator

__all__ = [
    "BaseGenerator",
    "GeneratorMode",
    "LocalGenerator",
    "StubGenerator",
]
