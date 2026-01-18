"""Anvil - JIT Infrastructure & Self-Healing SDK for AI Agents."""

from anvil.chain import ToolChain
from anvil.core import Anvil, Tool
from anvil.credentials import CredentialResolver
from anvil.generators import (
    BaseGenerator,
    GeneratorMode,
    LocalGenerator,
    StubGenerator,
)
from anvil.jit_generator import get_generator
from anvil.llm import LLMProvider, LLMResponse, ProviderFactory, get_provider
from anvil.logger import AnvilEvent, AnvilLogger, EventType
from anvil.models import InputParam, ToolConfig, ToolResult
from anvil.sandbox import SandboxManager, SandboxResult, SecurityPolicy

__version__ = "0.1.0"
__all__ = [
    # Core
    "Anvil",
    "Tool",
    "ToolChain",
    # Models
    "InputParam",
    "ToolConfig",
    "ToolResult",
    # Generators
    "BaseGenerator",
    "GeneratorMode",
    "LocalGenerator",
    "StubGenerator",
    "get_generator",
    # LLM Providers
    "LLMProvider",
    "LLMResponse",
    "ProviderFactory",
    "get_provider",
    # Credentials
    "CredentialResolver",
    # Logging
    "AnvilLogger",
    "AnvilEvent",
    "EventType",
    # Sandbox
    "SandboxManager",
    "SandboxResult",
    "SecurityPolicy",
]
