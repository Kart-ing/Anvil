"""Tests for Anvil CLI."""

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner

from anvil.cli import cli


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory."""
    return tmp_path


class TestCLIBasics:
    """Basic CLI tests."""

    def test_cli_help(self, runner):
        """Test CLI help message."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Anvil" in result.output
        assert "init" in result.output
        assert "doctor" in result.output
        assert "list" in result.output
        assert "clean" in result.output

    def test_cli_version(self, runner):
        """Test CLI version command."""
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestInitCommand:
    """Tests for anvil init command."""

    def test_init_creates_structure(self, runner, temp_project):
        """Test that init creates the expected structure."""
        result = runner.invoke(cli, ["init", "--dir", str(temp_project), "--skip-keys"])

        assert result.exit_code == 0
        assert "Anvil" in result.output

        # Check created files
        assert (temp_project / "anvil_tools").exists()
        assert (temp_project / "anvil_tools" / "__init__.py").exists()
        assert (temp_project / "anvil_tools" / "tool_registry.json").exists()
        assert (temp_project / ".env").exists()
        assert (temp_project / ".gitignore").exists()
        assert (temp_project / "example.py").exists()

    def test_init_custom_tools_dir(self, runner, temp_project):
        """Test init with custom tools directory name."""
        result = runner.invoke(cli, [
            "init",
            "--dir", str(temp_project),
            "--tools-dir", "my_tools",
            "--skip-keys"
        ])

        assert result.exit_code == 0
        assert (temp_project / "my_tools").exists()
        assert (temp_project / "my_tools" / "__init__.py").exists()

    def test_init_force_overwrites(self, runner, temp_project):
        """Test that --force overwrites existing files."""
        # Create existing file
        env_file = temp_project / ".env"
        env_file.write_text("OLD_CONTENT=true")

        result = runner.invoke(cli, [
            "init",
            "--dir", str(temp_project),
            "--force",
            "--skip-keys"
        ])

        assert result.exit_code == 0
        content = env_file.read_text()
        assert "ANTHROPIC_API_KEY" in content
        assert "OLD_CONTENT" not in content

    def test_init_preserves_existing_without_force(self, runner, temp_project):
        """Test that existing files are preserved without --force."""
        # Create existing env file
        env_file = temp_project / ".env"
        env_file.write_text("EXISTING_KEY=value")

        result = runner.invoke(cli, ["init", "--dir", str(temp_project), "--skip-keys"])

        assert result.exit_code == 0
        assert "already exists" in result.output


class TestDoctorCommand:
    """Tests for anvil doctor command."""

    def test_doctor_runs(self, runner):
        """Test that doctor command runs without error."""
        result = runner.invoke(cli, ["doctor"])
        assert result.exit_code == 0
        # Check for health check output (may have rich formatting)
        assert "Health Check" in result.output or "System" in result.output

    def test_doctor_checks_python(self, runner):
        """Test that doctor checks Python version."""
        result = runner.invoke(cli, ["doctor"])
        assert "Python" in result.output

    def test_doctor_checks_docker(self, runner):
        """Test that doctor checks Docker."""
        result = runner.invoke(cli, ["doctor"])
        assert "Docker" in result.output

    def test_doctor_checks_api_keys(self, runner):
        """Test that doctor checks API keys."""
        result = runner.invoke(cli, ["doctor"])
        assert "ANTHROPIC_API_KEY" in result.output


class TestListCommand:
    """Tests for anvil list command."""

    def test_list_empty_dir(self, runner, temp_project):
        """Test list with empty tools directory."""
        tools_dir = temp_project / "tools"
        tools_dir.mkdir()
        (tools_dir / "__init__.py").write_text("")

        result = runner.invoke(cli, ["list", "--dir", str(tools_dir)])
        assert result.exit_code == 0
        assert "No tools found" in result.output

    def test_list_nonexistent_dir(self, runner, temp_project):
        """Test list with nonexistent directory."""
        result = runner.invoke(cli, ["list", "--dir", str(temp_project / "nonexistent")])
        assert "not found" in result.output

    def test_list_with_tools(self, runner, temp_project):
        """Test list with some tools."""
        tools_dir = temp_project / "tools"
        tools_dir.mkdir()
        (tools_dir / "__init__.py").write_text("")
        (tools_dir / "tool_registry.json").write_text(json.dumps({
            "my_tool": {
                "version": "1.0",
                "intent": "Test tool",
                "status": "active"
            }
        }))
        (tools_dir / "my_tool.py").write_text("def run(): pass")

        result = runner.invoke(cli, ["list", "--dir", str(tools_dir)])
        assert result.exit_code == 0
        assert "my_tool" in result.output
        assert "1.0" in result.output

    def test_list_json_output(self, runner, temp_project):
        """Test list with JSON output."""
        tools_dir = temp_project / "tools"
        tools_dir.mkdir()
        (tools_dir / "__init__.py").write_text("")
        (tools_dir / "my_tool.py").write_text("def run(): pass")

        result = runner.invoke(cli, ["list", "--dir", str(tools_dir), "--json"])
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert "tools" in data
        assert len(data["tools"]) == 1
        assert data["tools"][0]["name"] == "my_tool"


class TestCleanCommand:
    """Tests for anvil clean command."""

    def test_clean_empty_dir(self, runner, temp_project):
        """Test clean with empty tools directory."""
        tools_dir = temp_project / "tools"
        tools_dir.mkdir()
        (tools_dir / "__init__.py").write_text("")

        result = runner.invoke(cli, ["clean", "--dir", str(tools_dir)])
        assert "No tools to clean" in result.output

    def test_clean_removes_tools(self, runner, temp_project):
        """Test that clean removes tool files."""
        tools_dir = temp_project / "tools"
        tools_dir.mkdir()
        (tools_dir / "__init__.py").write_text("")
        (tools_dir / "tool_registry.json").write_text("{}")

        # Create a tool
        tool_file = tools_dir / "my_tool.py"
        tool_file.write_text("""# ANVIL-MANAGED: true
def run(): pass
""")

        result = runner.invoke(cli, ["clean", "--dir", str(tools_dir), "--force"])
        assert result.exit_code == 0
        assert not tool_file.exists()

    def test_clean_keeps_ejected(self, runner, temp_project):
        """Test that --keep-ejected preserves ejected tools."""
        tools_dir = temp_project / "tools"
        tools_dir.mkdir()
        (tools_dir / "__init__.py").write_text("")
        (tools_dir / "tool_registry.json").write_text(json.dumps({
            "managed_tool": {"status": "active"},
            "ejected_tool": {"status": "ejected"},
        }))

        managed = tools_dir / "managed_tool.py"
        managed.write_text("# ANVIL-MANAGED: true\ndef run(): pass")

        ejected = tools_dir / "ejected_tool.py"
        ejected.write_text("# ANVIL-MANAGED: false\ndef run(): pass")

        result = runner.invoke(cli, [
            "clean",
            "--dir", str(tools_dir),
            "--force",
            "--keep-ejected"
        ])

        assert result.exit_code == 0
        assert not managed.exists()
        assert ejected.exists()


class TestVerifyCommand:
    """Tests for anvil verify command."""

    def test_verify_nonexistent_tool(self, runner, temp_project):
        """Test verify with nonexistent tool."""
        tools_dir = temp_project / "tools"
        tools_dir.mkdir()

        result = runner.invoke(cli, [
            "verify", "nonexistent",
            "--dir", str(tools_dir)
        ])
        assert "not found" in result.output

    def test_verify_safe_tool(self, runner, temp_project):
        """Test verify with safe code."""
        tools_dir = temp_project / "tools"
        tools_dir.mkdir()

        tool_file = tools_dir / "safe_tool.py"
        tool_file.write_text("""
import json

def run(**kwargs):
    return json.dumps({'status': 'ok'})

print(run())
""")

        result = runner.invoke(cli, [
            "verify", "safe_tool",
            "--dir", str(tools_dir)
        ])
        assert result.exit_code == 0
        # Should mention verification result
        assert "Verifying" in result.output

    def test_verify_dangerous_tool(self, runner, temp_project):
        """Test verify with dangerous code."""
        tools_dir = temp_project / "tools"
        tools_dir.mkdir()

        tool_file = tools_dir / "dangerous_tool.py"
        tool_file.write_text("""
import subprocess
subprocess.run(['rm', '-rf', '/'])
""")

        result = runner.invoke(cli, [
            "verify", "dangerous_tool",
            "--dir", str(tools_dir)
        ])
        # Should fail verification
        assert "failed" in result.output.lower() or "violation" in result.output.lower()
