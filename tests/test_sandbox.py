"""Tests for sandbox security module."""

import pytest

from anvil.sandbox import (
    DockerSandbox,
    LocalSandbox,
    SandboxManager,
    SandboxResult,
    SecurityPolicy,
    StaticAnalyzer,
)


class TestSecurityPolicy:
    """Tests for SecurityPolicy configuration."""

    def test_default_policy(self):
        """Test default security policy values."""
        policy = SecurityPolicy()
        assert policy.allow_network is False
        assert policy.allow_filesystem_write is False
        assert policy.allow_subprocess is False
        assert policy.max_memory_mb == 256

    def test_custom_policy(self):
        """Test custom security policy."""
        policy = SecurityPolicy(
            allow_network=True,
            max_memory_mb=512,
            blocked_imports=["os", "sys"],
        )
        assert policy.allow_network is True
        assert policy.max_memory_mb == 512
        assert "os" in policy.blocked_imports


class TestStaticAnalyzer:
    """Tests for static code analysis."""

    def test_detects_blocked_import(self):
        """Test detection of blocked imports."""
        policy = SecurityPolicy()
        analyzer = StaticAnalyzer(policy)

        code = """
import subprocess
def run(**kwargs):
    return subprocess.run(['ls'])
"""
        violations = analyzer.analyze(code)
        assert len(violations) > 0
        assert any("subprocess" in v for v in violations)

    def test_detects_from_import(self):
        """Test detection of blocked from imports."""
        policy = SecurityPolicy()
        analyzer = StaticAnalyzer(policy)

        code = """
from subprocess import run
def run(**kwargs):
    return run(['ls'])
"""
        violations = analyzer.analyze(code)
        assert len(violations) > 0
        assert any("subprocess" in v for v in violations)

    def test_detects_dangerous_os_calls(self):
        """Test detection of dangerous os.system calls."""
        policy = SecurityPolicy()
        analyzer = StaticAnalyzer(policy)

        code = """
import os
def run(**kwargs):
    os.system('rm -rf /')
    return {}
"""
        violations = analyzer.analyze(code)
        assert len(violations) > 0
        assert any("os.system" in v for v in violations)

    def test_allows_safe_code(self):
        """Test that safe code passes analysis."""
        policy = SecurityPolicy()
        analyzer = StaticAnalyzer(policy)

        code = """
import os
import json

def run(**kwargs):
    api_key = os.environ.get('API_KEY')
    return {'key_set': bool(api_key)}
"""
        violations = analyzer.analyze(code)
        assert len(violations) == 0

    def test_allows_network_when_permitted(self):
        """Test that socket import is allowed when network is permitted."""
        policy = SecurityPolicy(allow_network=True)
        analyzer = StaticAnalyzer(policy)

        code = """
import socket
def run(**kwargs):
    return {}
"""
        violations = analyzer.analyze(code)
        assert len(violations) == 0

    def test_detects_eval(self):
        """Test detection of eval() calls."""
        policy = SecurityPolicy()
        analyzer = StaticAnalyzer(policy)

        code = """
def run(**kwargs):
    user_input = kwargs.get('code', '')
    return eval(user_input)
"""
        violations = analyzer.analyze(code)
        assert len(violations) > 0
        assert any("eval" in v for v in violations)

    def test_syntax_error_reported(self):
        """Test that syntax errors are reported."""
        policy = SecurityPolicy()
        analyzer = StaticAnalyzer(policy)

        code = """
def run(**kwargs)
    return {}
"""
        violations = analyzer.analyze(code)
        assert len(violations) > 0
        assert any("Syntax error" in v for v in violations)


class TestLocalSandbox:
    """Tests for local sandbox execution."""

    def test_is_always_available(self):
        """Test that local sandbox is always available."""
        sandbox = LocalSandbox()
        assert sandbox.is_available() is True

    def test_executes_safe_code(self):
        """Test execution of safe code."""
        sandbox = LocalSandbox()
        code = """
def run(**kwargs):
    return {'result': 'success'}

print(run())
"""
        result = sandbox.execute(code)
        assert result.success is True
        assert "success" in result.output

    def test_rejects_dangerous_code(self):
        """Test that dangerous code is rejected."""
        sandbox = LocalSandbox()
        code = """
import subprocess
def run(**kwargs):
    subprocess.run(['ls'])
"""
        result = sandbox.execute(code)
        assert result.success is False
        assert result.security_violations is not None
        assert len(result.security_violations) > 0

    def test_handles_runtime_errors(self):
        """Test handling of runtime errors."""
        sandbox = LocalSandbox()
        code = """
def run(**kwargs):
    raise ValueError("Test error")

run()
"""
        result = sandbox.execute(code)
        assert result.success is False
        assert "ValueError" in (result.error or "")


class TestDockerSandbox:
    """Tests for Docker sandbox (may skip if Docker unavailable)."""

    @pytest.fixture
    def docker_sandbox(self):
        """Create a Docker sandbox instance."""
        return DockerSandbox()

    def test_availability_check(self, docker_sandbox):
        """Test Docker availability check."""
        # Just verify it doesn't crash
        available = docker_sandbox.is_available()
        assert isinstance(available, bool)

    @pytest.mark.skipif(
        not DockerSandbox().is_available(),
        reason="Docker not available"
    )
    def test_executes_safe_code(self, docker_sandbox):
        """Test execution of safe code in Docker."""
        code = """
print("Hello from Docker!")
"""
        result = docker_sandbox.execute(code, timeout=30)
        assert result.success is True
        assert "Hello from Docker" in (result.output or "")


class TestSandboxManager:
    """Tests for SandboxManager."""

    def test_initialization(self):
        """Test sandbox manager initialization."""
        manager = SandboxManager()
        assert manager.policy is not None
        assert manager._docker is not None
        assert manager._local is not None

    def test_get_driver_returns_local_when_no_docker(self):
        """Test that local driver is returned when Docker unavailable."""
        manager = SandboxManager(prefer_docker=False)
        driver = manager.get_driver()
        assert isinstance(driver, LocalSandbox)

    def test_get_status(self):
        """Test getting sandbox status."""
        manager = SandboxManager()
        status = manager.get_status()

        assert "docker_available" in status
        assert "active_driver" in status
        assert "policy" in status
        assert isinstance(status["docker_available"], bool)

    def test_verify_code_safe(self):
        """Test verification of safe code."""
        manager = SandboxManager(prefer_docker=False)
        code = """
import json

def run(**kwargs):
    return json.dumps({'status': 'ok'})

print(run())
"""
        result = manager.verify_code(code)
        # Should pass static analysis at minimum
        assert result.security_violations is None or len(result.security_violations) == 0

    def test_verify_code_dangerous(self):
        """Test verification of dangerous code."""
        manager = SandboxManager(prefer_docker=False)
        code = """
import subprocess
subprocess.run(['rm', '-rf', '/'])
"""
        result = manager.verify_code(code)
        assert result.success is False


class TestSandboxResult:
    """Tests for SandboxResult dataclass."""

    def test_success_result(self):
        """Test creating a success result."""
        result = SandboxResult(
            success=True,
            output="Hello World",
            duration_ms=100.5,
        )
        assert result.success is True
        assert result.output == "Hello World"
        assert result.error is None

    def test_failure_result(self):
        """Test creating a failure result."""
        result = SandboxResult(
            success=False,
            error="Code failed",
            security_violations=["Blocked import: subprocess"],
        )
        assert result.success is False
        assert result.error == "Code failed"
        assert len(result.security_violations) == 1


class TestAnvilIntegration:
    """Tests for sandbox integration with Anvil."""

    def test_anvil_has_sandbox(self, tmp_path):
        """Test that Anvil initializes with sandbox."""
        from anvil import Anvil

        anvil = Anvil(
            tools_dir=tmp_path / "tools",
            use_stub=True,
        )
        assert anvil._sandbox is not None
        assert isinstance(anvil._sandbox, SandboxManager)

    def test_anvil_sandbox_status(self, tmp_path):
        """Test getting sandbox status through Anvil."""
        from anvil import Anvil

        anvil = Anvil(
            tools_dir=tmp_path / "tools",
            use_stub=True,
        )
        status = anvil.get_sandbox_status()
        assert "docker_available" in status
        assert "active_driver" in status

    def test_anvil_verified_mode_flag(self, tmp_path):
        """Test that verified mode flag is set."""
        from anvil import Anvil

        anvil = Anvil(
            tools_dir=tmp_path / "tools",
            use_stub=True,
            verified_mode=True,
        )
        assert anvil.verified_mode is True

    def test_anvil_custom_security_policy(self, tmp_path):
        """Test Anvil with custom security policy."""
        from anvil import Anvil

        policy = SecurityPolicy(
            allow_network=True,
            max_memory_mb=512,
        )
        anvil = Anvil(
            tools_dir=tmp_path / "tools",
            use_stub=True,
            security_policy=policy,
        )
        assert anvil._sandbox.policy.allow_network is True
        assert anvil._sandbox.policy.max_memory_mb == 512
