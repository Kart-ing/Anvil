"""Sandbox module for secure code execution.

This module provides sandboxed execution environments to verify
generated code before saving it to the local filesystem.

Supported drivers:
1. DockerSandbox - Uses Docker containers for isolation
2. E2BSandbox - Uses E2B cloud sandboxes (optional)
3. LocalSandbox - Restricted local execution (fallback, less secure)
"""

import ast
import os
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SandboxResult:
    """Result from sandboxed code execution."""

    success: bool
    output: str | None = None
    error: str | None = None
    exit_code: int = 0
    duration_ms: float = 0
    security_violations: list[str] | None = None


@dataclass
class SecurityPolicy:
    """Security policy for sandbox execution."""

    # Network access
    allow_network: bool = False
    allowed_hosts: list[str] | None = None

    # Filesystem access
    allow_filesystem_read: bool = True
    allow_filesystem_write: bool = False
    allowed_paths: list[str] | None = None

    # System access
    allow_subprocess: bool = False
    allow_env_access: bool = True

    # Resource limits
    max_memory_mb: int = 256
    max_cpu_seconds: float = 30.0
    max_output_size_kb: int = 1024

    # Dangerous patterns to block
    blocked_imports: list[str] | None = None
    blocked_functions: list[str] | None = None

    def __post_init__(self) -> None:
        if self.blocked_imports is None:
            self.blocked_imports = [
                "subprocess",
                "multiprocessing",
                "ctypes",
                "socket",  # Unless network allowed
                "paramiko",
                "fabric",
                "shutil",  # Dangerous file operations
            ]
        if self.blocked_functions is None:
            self.blocked_functions = [
                "eval",
                "exec",
                "compile",
                "open",  # Unless filesystem write allowed
                "__import__",
                "getattr",
                "setattr",
                "delattr",
                "globals",
                "locals",
            ]


class StaticAnalyzer:
    """Static code analyzer for security checks."""

    def __init__(self, policy: SecurityPolicy):
        self.policy = policy

    def analyze(self, code: str) -> list[str]:
        """Analyze code for security violations.

        Args:
            code: Python source code to analyze

        Returns:
            List of security violation messages
        """
        violations: list[str] = []

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return [f"Syntax error: {e}"]

        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if self.policy.blocked_imports and alias.name in self.policy.blocked_imports:
                        if alias.name == "socket" and self.policy.allow_network:
                            continue
                        violations.append(f"Blocked import: {alias.name}")

            elif isinstance(node, ast.ImportFrom):
                if node.module and self.policy.blocked_imports:
                    if node.module.split(".")[0] in self.policy.blocked_imports:
                        if node.module == "socket" and self.policy.allow_network:
                            continue
                        violations.append(f"Blocked import: {node.module}")

            # Check dangerous function calls
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if self.policy.blocked_functions and node.func.id in self.policy.blocked_functions:
                        # Allow open() if filesystem write is permitted
                        if node.func.id == "open" and self.policy.allow_filesystem_write:
                            continue
                        violations.append(f"Blocked function call: {node.func.id}()")

                elif isinstance(node.func, ast.Attribute):
                    # Check for os.system, subprocess.run, etc.
                    if isinstance(node.func.value, ast.Name):
                        full_name = f"{node.func.value.id}.{node.func.attr}"
                        dangerous_calls = [
                            "os.system",
                            "os.popen",
                            "os.spawn",
                            "os.exec",
                            "os.remove",
                            "os.rmdir",
                            "os.unlink",
                            "shutil.rmtree",
                            "shutil.move",
                        ]
                        if not self.policy.allow_subprocess:
                            dangerous_calls.extend([
                                "subprocess.run",
                                "subprocess.call",
                                "subprocess.Popen",
                                "subprocess.check_output",
                            ])
                        if full_name in dangerous_calls:
                            violations.append(f"Dangerous call: {full_name}()")

        return violations


class SandboxDriver(ABC):
    """Abstract base class for sandbox drivers."""

    def __init__(self, policy: SecurityPolicy | None = None):
        self.policy = policy or SecurityPolicy()
        self.analyzer = StaticAnalyzer(self.policy)

    @abstractmethod
    def execute(self, code: str, timeout: float = 30.0) -> SandboxResult:
        """Execute code in the sandbox.

        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds

        Returns:
            SandboxResult with execution details
        """
        pass

    def verify(self, code: str) -> SandboxResult:
        """Verify code is safe to execute.

        Performs static analysis and optionally runs in sandbox.

        Args:
            code: Python code to verify

        Returns:
            SandboxResult indicating if code is safe
        """
        # Static analysis first
        violations = self.analyzer.analyze(code)
        if violations:
            return SandboxResult(
                success=False,
                error="Security policy violations detected",
                security_violations=violations,
            )

        # Then try to execute in sandbox
        return self.execute(code)

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this sandbox driver is available."""
        pass


class DockerSandbox(SandboxDriver):
    """Docker-based sandbox for secure code execution."""

    def __init__(
        self,
        policy: SecurityPolicy | None = None,
        image: str = "python:3.11-slim",
    ):
        super().__init__(policy)
        self.image = image
        self._docker_available: bool | None = None

    def is_available(self) -> bool:
        """Check if Docker is available and running."""
        if self._docker_available is not None:
            return self._docker_available

        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            self._docker_available = result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            self._docker_available = False

        return self._docker_available

    def execute(self, code: str, timeout: float = 30.0) -> SandboxResult:
        """Execute code in a Docker container.

        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds

        Returns:
            SandboxResult with execution details
        """
        if not self.is_available():
            return SandboxResult(
                success=False,
                error="Docker is not available. Run 'anvil doctor' to diagnose.",
            )

        start_time = time.perf_counter()

        # Create temp file with the code
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Build docker run command with security restrictions
            cmd = [
                "docker", "run",
                "--rm",  # Remove container after execution
                "--network", "none" if not self.policy.allow_network else "bridge",
                "--memory", f"{self.policy.max_memory_mb}m",
                "--cpus", "1",
                "--read-only" if not self.policy.allow_filesystem_write else "",
                "-v", f"{temp_path}:/code/script.py:ro",
                "-w", "/code",
                self.image,
                "python", "script.py",
            ]
            # Remove empty strings
            cmd = [c for c in cmd if c]

            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                text=True,
            )

            duration_ms = (time.perf_counter() - start_time) * 1000

            if result.returncode == 0:
                return SandboxResult(
                    success=True,
                    output=result.stdout[:self.policy.max_output_size_kb * 1024],
                    exit_code=result.returncode,
                    duration_ms=duration_ms,
                )
            else:
                return SandboxResult(
                    success=False,
                    output=result.stdout,
                    error=result.stderr,
                    exit_code=result.returncode,
                    duration_ms=duration_ms,
                )

        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout}s",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return SandboxResult(
                success=False,
                error=f"Docker execution failed: {e}",
                duration_ms=duration_ms,
            )
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class LocalSandbox(SandboxDriver):
    """Local sandbox using restricted execution.

    WARNING: This is less secure than Docker. Use only as fallback.
    Relies primarily on static analysis for security.
    """

    def is_available(self) -> bool:
        """Local sandbox is always available."""
        return True

    def execute(self, code: str, timeout: float = 30.0) -> SandboxResult:
        """Execute code in a restricted local environment.

        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds

        Returns:
            SandboxResult with execution details
        """
        start_time = time.perf_counter()

        # Static analysis is critical for local sandbox
        violations = self.analyzer.analyze(code)
        if violations:
            return SandboxResult(
                success=False,
                error="Code failed security checks",
                security_violations=violations,
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Create temp file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False
        ) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run in subprocess with limited privileges
            result = subprocess.run(
                ["python", temp_path],
                capture_output=True,
                timeout=timeout,
                text=True,
                env={
                    **os.environ,
                    "PYTHONDONTWRITEBYTECODE": "1",
                },
            )

            duration_ms = (time.perf_counter() - start_time) * 1000

            if result.returncode == 0:
                return SandboxResult(
                    success=True,
                    output=result.stdout[:self.policy.max_output_size_kb * 1024],
                    exit_code=result.returncode,
                    duration_ms=duration_ms,
                )
            else:
                return SandboxResult(
                    success=False,
                    output=result.stdout,
                    error=result.stderr,
                    exit_code=result.returncode,
                    duration_ms=duration_ms,
                )

        except subprocess.TimeoutExpired:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return SandboxResult(
                success=False,
                error=f"Execution timed out after {timeout}s",
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return SandboxResult(
                success=False,
                error=f"Execution failed: {e}",
                duration_ms=duration_ms,
            )
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class SandboxManager:
    """Manages sandbox drivers and provides unified interface."""

    def __init__(
        self,
        policy: SecurityPolicy | None = None,
        prefer_docker: bool = True,
    ):
        """Initialize sandbox manager.

        Args:
            policy: Security policy to enforce
            prefer_docker: If True, use Docker when available
        """
        self.policy = policy or SecurityPolicy()
        self.prefer_docker = prefer_docker

        # Initialize drivers
        self._docker = DockerSandbox(policy=self.policy)
        self._local = LocalSandbox(policy=self.policy)

    def get_driver(self) -> SandboxDriver:
        """Get the best available sandbox driver.

        Returns:
            SandboxDriver instance
        """
        if self.prefer_docker and self._docker.is_available():
            return self._docker
        return self._local

    def verify_code(self, code: str) -> SandboxResult:
        """Verify code is safe to execute.

        Args:
            code: Python code to verify

        Returns:
            SandboxResult indicating if code passed verification
        """
        driver = self.get_driver()
        return driver.verify(code)

    def execute(self, code: str, timeout: float = 30.0) -> SandboxResult:
        """Execute code in the sandbox.

        Args:
            code: Python code to execute
            timeout: Maximum execution time

        Returns:
            SandboxResult with execution details
        """
        driver = self.get_driver()
        return driver.execute(code, timeout=timeout)

    def get_status(self) -> dict[str, Any]:
        """Get status of sandbox drivers.

        Returns:
            Dict with driver availability info
        """
        return {
            "docker_available": self._docker.is_available(),
            "active_driver": "docker" if (
                self.prefer_docker and self._docker.is_available()
            ) else "local",
            "policy": {
                "allow_network": self.policy.allow_network,
                "allow_filesystem_write": self.policy.allow_filesystem_write,
                "allow_subprocess": self.policy.allow_subprocess,
                "max_memory_mb": self.policy.max_memory_mb,
                "max_cpu_seconds": self.policy.max_cpu_seconds,
            },
        }


# Default sandbox manager instance
_default_sandbox: SandboxManager | None = None


def get_sandbox(policy: SecurityPolicy | None = None) -> SandboxManager:
    """Get or create the default sandbox manager.

    Args:
        policy: Optional security policy to use

    Returns:
        SandboxManager instance
    """
    global _default_sandbox
    if _default_sandbox is None or policy is not None:
        _default_sandbox = SandboxManager(policy=policy)
    return _default_sandbox
