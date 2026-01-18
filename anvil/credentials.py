"""Credential resolver for handling missing API keys interactively.

This module provides intelligent credential resolution that:
1. Detects missing API keys from tool execution results
2. Prompts the user to provide them interactively
3. Optionally persists them to .env files for future use
4. Retries tool execution with the resolved credentials
"""

import os
import re
from pathlib import Path
from typing import Any


# Common patterns for detecting missing API key errors
API_KEY_PATTERNS = [
    # Environment variable patterns
    r"(?:environment variable|env var|env)\s+['\"]?([A-Z][A-Z0-9_]*(?:_API_KEY|_KEY|_TOKEN|_SECRET))['\"]?\s+(?:not set|not found|missing|is required|required)",
    r"([A-Z][A-Z0-9_]*(?:_API_KEY|_KEY|_TOKEN|_SECRET))\s+(?:not set|not found|missing|is required)",
    r"(?:missing|no|set)\s+([A-Z][A-Z0-9_]*(?:_API_KEY|_KEY|_TOKEN|_SECRET))",
    # Generic API key mentions
    r"(?:api[_\s]?key|token|secret)\s+(?:for\s+)?['\"]?(\w+)['\"]?\s+(?:not|is\s+not|missing)",
    # Error dict patterns (common in generated code)
    r"['\"]?([A-Z][A-Z0-9_]*(?:_API_KEY|_KEY|_TOKEN|_SECRET))['\"]?\s+environment variable not set",
]

# Well-known API keys and their help URLs
KNOWN_API_KEYS: dict[str, dict[str, str]] = {
    "ANTHROPIC_API_KEY": {
        "name": "Anthropic API Key",
        "url": "https://console.anthropic.com/settings/keys",
        "description": "Required for Claude AI integration",
    },
    "OPENAI_API_KEY": {
        "name": "OpenAI API Key",
        "url": "https://platform.openai.com/api-keys",
        "description": "Required for OpenAI/GPT integration",
    },
    "FIRECRAWL_API_KEY": {
        "name": "FireCrawl API Key",
        "url": "https://www.firecrawl.dev/",
        "description": "Required for web scraping documentation",
    },
    "ALPHA_VANTAGE_API_KEY": {
        "name": "Alpha Vantage API Key",
        "url": "https://www.alphavantage.co/support/#api-key",
        "description": "Required for stock market data (free tier available)",
    },
    "WEATHER_API_KEY": {
        "name": "Weather API Key",
        "url": "https://www.weatherapi.com/",
        "description": "Required for weather data",
    },
    "NOTION_API_KEY": {
        "name": "Notion API Key",
        "url": "https://www.notion.so/my-integrations",
        "description": "Required for Notion workspace integration",
    },
    "GITHUB_TOKEN": {
        "name": "GitHub Personal Access Token",
        "url": "https://github.com/settings/tokens",
        "description": "Required for GitHub API access",
    },
    "SLACK_BOT_TOKEN": {
        "name": "Slack Bot Token",
        "url": "https://api.slack.com/apps",
        "description": "Required for Slack integration",
    },
}


class CredentialResolver:
    """Handles interactive resolution of missing credentials."""

    def __init__(
        self,
        env_file: Path | str | None = None,
        interactive: bool = True,
        auto_persist: bool = False,
    ):
        """Initialize the credential resolver.

        Args:
            env_file: Path to .env file for persistence (default: ./.env)
            interactive: If True, prompt user for missing credentials
            auto_persist: If True, automatically save to .env without asking
        """
        self.env_file = Path(env_file) if env_file else Path(".env")
        self.interactive = interactive
        self.auto_persist = auto_persist
        # Session cache for credentials entered this session
        self._session_cache: dict[str, str] = {}

    def detect_missing_credential(self, result: Any) -> str | None:
        """Detect if a tool result indicates a missing API key.

        Args:
            result: The result from tool execution (can be dict, str, or any type)

        Returns:
            The name of the missing environment variable, or None if not detected
        """
        # Check for standardized missing_credential key first (most reliable)
        if isinstance(result, dict):
            if "missing_credential" in result:
                return result["missing_credential"]
            # Check for common error patterns in dicts
            error_text = str(result.get("error", "")) + str(result.get("message", ""))
            result_str = error_text if error_text else str(result)
        else:
            result_str = str(result)

        # Try each pattern
        for pattern in API_KEY_PATTERNS:
            match = re.search(pattern, result_str, re.IGNORECASE)
            if match:
                key_name = match.group(1).upper()
                # Validate it looks like an env var name
                if re.match(r"^[A-Z][A-Z0-9_]*$", key_name):
                    return key_name

        return None

    def get_key_info(self, key_name: str) -> dict[str, str]:
        """Get information about a known API key.

        Args:
            key_name: The environment variable name

        Returns:
            Dict with name, url, and description (may be generic if unknown)
        """
        if key_name in KNOWN_API_KEYS:
            return KNOWN_API_KEYS[key_name]

        # Generate generic info
        readable_name = key_name.replace("_", " ").title()
        return {
            "name": readable_name,
            "url": "",
            "description": f"Required by the tool (check tool documentation)",
        }

    def prompt_for_credential(self, key_name: str) -> str | None:
        """Interactively prompt the user for a missing credential.

        Args:
            key_name: The environment variable name needed

        Returns:
            The credential value entered by the user, or None if cancelled
        """
        if not self.interactive:
            return None

        key_info = self.get_key_info(key_name)

        print(f"\n{'='*60}")
        print(f"  Missing Credential: {key_info['name']}")
        print(f"{'='*60}")
        print(f"\nThe tool requires: {key_name}")
        print(f"Description: {key_info['description']}")

        if key_info["url"]:
            print(f"\nGet your key here: {key_info['url']}")

        print(f"\nOptions:")
        print(f"  1. Enter the API key now")
        print(f"  2. Skip (tool will fail)")
        print()

        try:
            choice = input("Your choice [1/2]: ").strip()

            if choice == "2":
                print("Skipped. Tool will continue without the credential.")
                return None

            # Default to option 1
            value = input(f"\nEnter {key_name}: ").strip()

            if not value:
                print("No value entered. Skipping.")
                return None

            # Ask about persistence
            if not self.auto_persist:
                save = input(f"\nSave to {self.env_file}? [y/N]: ").strip().lower()
                if save in ("y", "yes"):
                    self._persist_credential(key_name, value)
                    print(f"Saved to {self.env_file}")

            # Set in environment for current session
            os.environ[key_name] = value
            self._session_cache[key_name] = value

            print(f"\n{key_name} set for this session.")
            return value

        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            return None

    def _persist_credential(self, key_name: str, value: str) -> None:
        """Save a credential to the .env file.

        Args:
            key_name: Environment variable name
            value: The value to save
        """
        # Read existing content
        existing_content = ""
        if self.env_file.exists():
            existing_content = self.env_file.read_text()

        # Check if key already exists
        pattern = rf"^{re.escape(key_name)}=.*$"
        if re.search(pattern, existing_content, re.MULTILINE):
            # Replace existing
            new_content = re.sub(
                pattern,
                f'{key_name}="{value}"',
                existing_content,
                flags=re.MULTILINE,
            )
        else:
            # Append new
            if existing_content and not existing_content.endswith("\n"):
                existing_content += "\n"
            new_content = existing_content + f'{key_name}="{value}"\n'

        self.env_file.write_text(new_content)

    def resolve_and_retry(
        self,
        result: Any,
        retry_func: Any,
        **kwargs: Any,
    ) -> tuple[bool, Any]:
        """Attempt to resolve a missing credential and retry the operation.

        Args:
            result: The failed result that may indicate missing credentials
            retry_func: Function to call for retry (should accept **kwargs)
            **kwargs: Arguments to pass to retry_func

        Returns:
            Tuple of (was_resolved, new_result)
            - was_resolved: True if we detected and resolved a credential
            - new_result: Result from retry, or original result if not resolved
        """
        key_name = self.detect_missing_credential(result)

        if not key_name:
            return (False, result)

        # Check if already in session cache (avoid re-prompting)
        if key_name in self._session_cache:
            return (False, result)

        # Check if already set in environment
        if os.environ.get(key_name):
            return (False, result)

        # Prompt for the credential
        value = self.prompt_for_credential(key_name)

        if not value:
            return (False, result)

        # Retry the operation
        try:
            new_result = retry_func(**kwargs)
            return (True, new_result)
        except Exception as e:
            return (True, {"error": str(e)})

    def clear_session_cache(self) -> None:
        """Clear the session credential cache."""
        self._session_cache.clear()


# Default resolver instance
_default_resolver: CredentialResolver | None = None


def get_default_resolver() -> CredentialResolver:
    """Get or create the default credential resolver."""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = CredentialResolver()
    return _default_resolver


def set_default_resolver(resolver: CredentialResolver) -> None:
    """Set the default credential resolver."""
    global _default_resolver
    _default_resolver = resolver
