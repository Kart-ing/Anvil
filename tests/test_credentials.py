"""Tests for credential resolver functionality."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from anvil import Anvil, CredentialResolver


class TestCredentialDetection:
    """Tests for detecting missing credentials in results."""

    def test_detect_standardized_pattern(self):
        """Test detection of standardized missing_credential key."""
        resolver = CredentialResolver(interactive=False)
        result = {
            "error": "API key not set",
            "missing_credential": "ALPHA_VANTAGE_API_KEY",
        }
        assert resolver.detect_missing_credential(result) == "ALPHA_VANTAGE_API_KEY"

    def test_detect_env_var_not_set_pattern(self):
        """Test detection of 'environment variable not set' pattern."""
        resolver = CredentialResolver(interactive=False)
        result = {"error": "OPENAI_API_KEY environment variable not set"}
        assert resolver.detect_missing_credential(result) == "OPENAI_API_KEY"

    def test_detect_not_found_pattern(self):
        """Test detection of 'not found' pattern."""
        resolver = CredentialResolver(interactive=False)
        result = {"error": "Environment variable GITHUB_TOKEN not found"}
        assert resolver.detect_missing_credential(result) == "GITHUB_TOKEN"

    def test_detect_missing_pattern(self):
        """Test detection of 'missing' pattern."""
        resolver = CredentialResolver(interactive=False)
        result = {"error": "Missing SLACK_BOT_TOKEN"}
        assert resolver.detect_missing_credential(result) == "SLACK_BOT_TOKEN"

    def test_no_detection_for_normal_error(self):
        """Test that normal errors don't trigger false positives."""
        resolver = CredentialResolver(interactive=False)
        result = {"error": "Network connection failed"}
        assert resolver.detect_missing_credential(result) is None

    def test_no_detection_for_success(self):
        """Test that successful results don't trigger detection."""
        resolver = CredentialResolver(interactive=False)
        result = {"data": "some value", "status": "ok"}
        assert resolver.detect_missing_credential(result) is None

    def test_detect_from_string(self):
        """Test detection from string result."""
        resolver = CredentialResolver(interactive=False)
        result = "Error: FIRECRAWL_API_KEY is required but not set"
        assert resolver.detect_missing_credential(result) == "FIRECRAWL_API_KEY"


class TestKnownApiKeys:
    """Tests for known API key information."""

    def test_get_known_key_info(self):
        """Test getting info for a known API key."""
        resolver = CredentialResolver(interactive=False)
        info = resolver.get_key_info("ANTHROPIC_API_KEY")
        assert info["name"] == "Anthropic API Key"
        assert "console.anthropic.com" in info["url"]
        assert info["description"]

    def test_get_unknown_key_info(self):
        """Test getting info for an unknown API key."""
        resolver = CredentialResolver(interactive=False)
        info = resolver.get_key_info("MY_CUSTOM_API_KEY")
        assert info["name"] == "My Custom Api Key"  # Humanized
        assert info["url"] == ""  # No known URL
        assert "tool documentation" in info["description"].lower()


class TestCredentialPersistence:
    """Tests for .env file persistence."""

    def test_persist_new_credential(self, tmp_path):
        """Test saving a new credential to .env file."""
        env_file = tmp_path / ".env"
        resolver = CredentialResolver(env_file=env_file, interactive=False)

        resolver._persist_credential("TEST_API_KEY", "test_value_123")

        content = env_file.read_text()
        assert 'TEST_API_KEY="test_value_123"' in content

    def test_persist_updates_existing(self, tmp_path):
        """Test updating an existing credential in .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text('TEST_API_KEY="old_value"\nOTHER_KEY="keep"\n')

        resolver = CredentialResolver(env_file=env_file, interactive=False)
        resolver._persist_credential("TEST_API_KEY", "new_value")

        content = env_file.read_text()
        assert 'TEST_API_KEY="new_value"' in content
        assert 'OTHER_KEY="keep"' in content
        assert "old_value" not in content

    def test_persist_appends_to_existing(self, tmp_path):
        """Test appending new credential to existing .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text('EXISTING_KEY="value"\n')

        resolver = CredentialResolver(env_file=env_file, interactive=False)
        resolver._persist_credential("NEW_API_KEY", "new_value")

        content = env_file.read_text()
        assert 'EXISTING_KEY="value"' in content
        assert 'NEW_API_KEY="new_value"' in content


class TestInteractivePrompt:
    """Tests for interactive credential prompting."""

    def test_prompt_disabled_returns_none(self):
        """Test that prompt returns None when interactive is disabled."""
        resolver = CredentialResolver(interactive=False)
        result = resolver.prompt_for_credential("TEST_API_KEY")
        assert result is None

    def test_prompt_with_user_input(self, tmp_path):
        """Test prompting user for credential."""
        env_file = tmp_path / ".env"
        resolver = CredentialResolver(env_file=env_file, interactive=True)

        # Mock user input: choose option 1, enter key, decline save
        with patch("builtins.input", side_effect=["1", "my_secret_key", "n"]):
            result = resolver.prompt_for_credential("TEST_API_KEY")

        assert result == "my_secret_key"
        assert os.environ.get("TEST_API_KEY") == "my_secret_key"
        # Clean up
        del os.environ["TEST_API_KEY"]

    def test_prompt_user_skips(self, tmp_path):
        """Test user choosing to skip credential entry."""
        resolver = CredentialResolver(env_file=tmp_path / ".env", interactive=True)

        # Mock user input: choose option 2 (skip)
        with patch("builtins.input", return_value="2"):
            result = resolver.prompt_for_credential("TEST_API_KEY")

        assert result is None

    def test_prompt_saves_to_env_file(self, tmp_path):
        """Test that user can save credential to .env file."""
        env_file = tmp_path / ".env"
        resolver = CredentialResolver(env_file=env_file, interactive=True)

        # Mock user input: choose option 1, enter key, accept save
        with patch("builtins.input", side_effect=["1", "persistent_key", "y"]):
            result = resolver.prompt_for_credential("SAVED_API_KEY")

        assert result == "persistent_key"
        assert 'SAVED_API_KEY="persistent_key"' in env_file.read_text()
        # Clean up
        del os.environ["SAVED_API_KEY"]


class TestSessionCache:
    """Tests for session-level credential caching."""

    def test_session_cache_stores_entered_credentials(self, tmp_path):
        """Test that entered credentials are cached for the session."""
        resolver = CredentialResolver(env_file=tmp_path / ".env", interactive=True)

        with patch("builtins.input", side_effect=["1", "cached_value", "n"]):
            resolver.prompt_for_credential("CACHED_KEY")

        assert "CACHED_KEY" in resolver._session_cache
        assert resolver._session_cache["CACHED_KEY"] == "cached_value"
        # Clean up
        del os.environ["CACHED_KEY"]

    def test_clear_session_cache(self, tmp_path):
        """Test clearing the session cache."""
        resolver = CredentialResolver(env_file=tmp_path / ".env", interactive=True)
        resolver._session_cache["KEY1"] = "value1"
        resolver._session_cache["KEY2"] = "value2"

        resolver.clear_session_cache()

        assert len(resolver._session_cache) == 0


class TestAnvilIntegration:
    """Tests for Anvil integration with credential resolver."""

    def test_anvil_initializes_with_credential_resolver(self, tmp_path):
        """Test that Anvil creates a credential resolver."""
        anvil = Anvil(
            tools_dir=tmp_path / "tools",
            use_stub=True,
            interactive_credentials=True,
        )

        assert anvil._credential_resolver is not None
        assert anvil._credential_resolver.interactive is True

    def test_anvil_respects_interactive_credentials_flag(self, tmp_path):
        """Test that Anvil respects the interactive_credentials flag."""
        anvil = Anvil(
            tools_dir=tmp_path / "tools",
            use_stub=True,
            interactive_credentials=False,
        )

        assert anvil.interactive_credentials is False
        assert anvil._credential_resolver.interactive is False

    def test_anvil_uses_custom_env_file(self, tmp_path):
        """Test that Anvil uses custom .env file path."""
        env_file = tmp_path / "custom.env"
        anvil = Anvil(
            tools_dir=tmp_path / "tools",
            use_stub=True,
            env_file=env_file,
        )

        assert anvil._credential_resolver.env_file == env_file


class TestToolCredentialResolution:
    """Tests for credential resolution during tool execution."""

    def test_tool_detects_missing_credential_in_result(self, tmp_path):
        """Test that tool detects missing credential from result dict."""
        anvil = Anvil(
            tools_dir=tmp_path / "tools",
            use_stub=True,
            interactive_credentials=False,  # Disable for this test
        )

        # Create a tool that returns a missing credential error
        tool_code = '''
def run(**kwargs):
    return {
        "error": "TEST_API_KEY environment variable not set",
        "missing_credential": "TEST_API_KEY"
    }
'''
        tool_path = tmp_path / "tools" / "test_tool.py"
        tool_path.parent.mkdir(parents=True, exist_ok=True)
        tool_path.write_text(tool_code)

        tool = anvil.use_tool(name="test_tool", intent="test")

        # With interactive disabled, should return the error dict
        result = tool.run()
        assert isinstance(result, dict)
        assert "missing_credential" in result

    def test_credential_resolution_triggers_on_missing_key(self, tmp_path):
        """Test that credential resolution is triggered for missing keys."""
        env_file = tmp_path / "test.env"
        anvil = Anvil(
            tools_dir=tmp_path / "tools",
            use_stub=True,
            interactive_credentials=True,
            env_file=env_file,
        )

        # Create a tool that checks for an env var
        tool_code = '''
import os
def run(**kwargs):
    key = os.environ.get("DYNAMIC_API_KEY")
    if not key:
        return {
            "error": "DYNAMIC_API_KEY environment variable not set",
            "missing_credential": "DYNAMIC_API_KEY"
        }
    return {"status": "success", "key_length": len(key)}
'''
        tool_path = tmp_path / "tools" / "dynamic_tool.py"
        tool_path.parent.mkdir(parents=True, exist_ok=True)
        tool_path.write_text(tool_code)

        tool = anvil.use_tool(name="dynamic_tool", intent="test dynamic")

        # Mock user providing the credential
        with patch("builtins.input", side_effect=["1", "my_dynamic_key", "n"]):
            result = tool.run()

        # Tool should have been re-executed with the credential
        assert result["status"] == "success"
        assert result["key_length"] == len("my_dynamic_key")

        # Clean up
        if "DYNAMIC_API_KEY" in os.environ:
            del os.environ["DYNAMIC_API_KEY"]


class TestResolveAndRetry:
    """Tests for the resolve_and_retry functionality."""

    def test_resolve_and_retry_with_matching_credential(self, tmp_path):
        """Test resolve_and_retry when credential is detected."""
        resolver = CredentialResolver(
            env_file=tmp_path / ".env",
            interactive=True,
        )

        call_count = 0

        def retry_func(**kwargs):
            nonlocal call_count
            call_count += 1
            if os.environ.get("RETRY_TEST_KEY"):
                return {"success": True}
            return {"error": "RETRY_TEST_KEY not set"}

        initial_result = {"error": "RETRY_TEST_KEY environment variable not set"}

        with patch("builtins.input", side_effect=["1", "retry_value", "n"]):
            was_resolved, new_result = resolver.resolve_and_retry(
                initial_result, retry_func
            )

        assert was_resolved is True
        assert new_result == {"success": True}
        assert call_count == 1

        # Clean up
        if "RETRY_TEST_KEY" in os.environ:
            del os.environ["RETRY_TEST_KEY"]

    def test_resolve_and_retry_no_credential_detected(self, tmp_path):
        """Test resolve_and_retry when no credential issue is detected."""
        resolver = CredentialResolver(
            env_file=tmp_path / ".env",
            interactive=True,
        )

        def retry_func(**kwargs):
            return {"should_not": "be_called"}

        initial_result = {"error": "Some other error"}

        was_resolved, new_result = resolver.resolve_and_retry(
            initial_result, retry_func
        )

        assert was_resolved is False
        assert new_result == initial_result
