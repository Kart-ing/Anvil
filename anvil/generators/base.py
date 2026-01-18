"""Base generator interface for Anvil tool generation.

This module defines the abstract interface that all generators must implement,
enabling both local (BYO keys) and cloud (Anvil Cloud) generation modes.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from anvil.models import GeneratedCode, ToolConfig


class GeneratorMode(str, Enum):
    """Available generator modes."""

    LOCAL = "local"  # BYO API keys, generate locally
    CLOUD = "cloud"  # Use Anvil Cloud (future)
    STUB = "stub"  # Testing mode, no real generation


class BaseGenerator(ABC):
    """Abstract base class for tool generators.

    All generators must implement these methods to be compatible
    with the Anvil runtime.
    """

    @property
    @abstractmethod
    def mode(self) -> GeneratorMode:
        """Return the generator mode."""
        pass

    @abstractmethod
    def fetch_documentation(self, docs_url: str | None) -> str:
        """Fetch documentation from a URL.

        Args:
            docs_url: URL to scrape for documentation

        Returns:
            Extracted documentation text, or empty string if unavailable
        """
        pass

    @abstractmethod
    def generate(self, config: ToolConfig) -> GeneratedCode:
        """Generate tool code based on intent and docs.

        Args:
            config: Tool configuration with name, intent, docs_url

        Returns:
            GeneratedCode with the Python code and dependencies
        """
        pass

    @abstractmethod
    def generate_fix(
        self,
        config: ToolConfig,
        previous_code: str,
        error_message: str,
    ) -> GeneratedCode:
        """Generate fixed code after a failure.

        Args:
            config: Tool configuration
            previous_code: The code that failed
            error_message: The error that occurred

        Returns:
            GeneratedCode with the fixed Python code
        """
        pass

    async def generate_async(self, config: ToolConfig) -> GeneratedCode:
        """Async version of generate.

        Default implementation calls sync version.
        Override for true async support.

        Args:
            config: Tool configuration

        Returns:
            GeneratedCode with the Python code
        """
        return self.generate(config)

    async def generate_fix_async(
        self,
        config: ToolConfig,
        previous_code: str,
        error_message: str,
    ) -> GeneratedCode:
        """Async version of generate_fix.

        Default implementation calls sync version.
        Override for true async support.

        Args:
            config: Tool configuration
            previous_code: The code that failed
            error_message: The error that occurred

        Returns:
            GeneratedCode with the fixed Python code
        """
        return self.generate_fix(config, previous_code, error_message)
