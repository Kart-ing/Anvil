"""Anvil Ingest - Scan and register existing tools for Anvil management.

This module provides functionality to:
1. Scan a directory of existing Python tool files
2. Analyze their structure (find run() functions, extract docstrings)
3. Wrap them with Anvil management headers
4. Create a manifest for tracking tool health and status

Usage:
    from anvil.ingest import ToolIngester

    ingester = ToolIngester(
        source_dir="./my_tools",
        managed_dir="./anvil_managed",
    )
    manifest = ingester.scan_and_register()
"""

import ast
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ToolInfo:
    """Information about a discovered tool."""

    name: str
    source_file: Path
    description: str = ""
    has_run_function: bool = False
    parameters: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    status: str = "pending"  # pending, healthy, broken, repairing
    error: str | None = None
    last_check: str | None = None


@dataclass
class IngestManifest:
    """Manifest tracking all ingested tools."""

    version: str = "1.0"
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    source_dir: str = ""
    managed_dir: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert manifest to dictionary."""
        stats = {
            "total": len(self.tools),
            "healthy": sum(1 for t in self.tools if t.get("status") == "healthy"),
            "broken": sum(1 for t in self.tools if t.get("status") == "broken"),
            "pending": sum(1 for t in self.tools if t.get("status") == "pending"),
            "repairing": sum(1 for t in self.tools if t.get("status") == "repairing"),
        }
        return {
            "version": self.version,
            "created": self.created,
            "source_dir": self.source_dir,
            "managed_dir": self.managed_dir,
            "tools": self.tools,
            "stats": stats,
        }

    def save(self, path: Path) -> None:
        """Save manifest to file."""
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, path: Path) -> "IngestManifest":
        """Load manifest from file."""
        data = json.loads(path.read_text())
        manifest = cls(
            version=data.get("version", "1.0"),
            created=data.get("created", ""),
            source_dir=data.get("source_dir", ""),
            managed_dir=data.get("managed_dir", ""),
            tools=data.get("tools", []),
        )
        return manifest


class ToolAnalyzer:
    """Analyzes Python files to extract tool information."""

    @staticmethod
    def analyze(file_path: Path) -> ToolInfo:
        """Analyze a Python file and extract tool information."""
        code = file_path.read_text()
        tool = ToolInfo(
            name=file_path.stem,
            source_file=file_path,
        )

        try:
            tree = ast.parse(code)
        except SyntaxError:
            tool.status = "broken"
            tool.error = "Syntax error in source file"
            return tool

        # Extract module docstring
        if (tree.body and
            isinstance(tree.body[0], ast.Expr) and
            isinstance(tree.body[0].value, ast.Constant)):
            docstring = tree.body[0].value.value
            if isinstance(docstring, str):
                tool.description = docstring.strip().split("\n")[0]

        # Find imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    tool.imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    tool.imports.append(node.module)

        # Find run() function
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "run":
                tool.has_run_function = True

                # Extract parameters
                for arg in node.args.args:
                    if arg.arg != "self":
                        tool.parameters.append(arg.arg)

                # Extract function docstring
                if (node.body and
                    isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant)):
                    func_doc = node.body[0].value.value
                    if isinstance(func_doc, str) and not tool.description:
                        tool.description = func_doc.strip().split("\n")[0]

                break

        if not tool.has_run_function:
            tool.status = "broken"
            tool.error = "Missing run() function"

        return tool


class ToolIngester:
    """Ingests existing tools into Anvil management."""

    WRAPPER_TEMPLATE = '''# ANVIL MANAGED TOOL
# ═══════════════════════════════════════════════════════════════════════════════
# Original: {source_file}
# Ingested: {timestamp}
# Status: managed
# ANVIL-MANAGED: true
#
# This tool is monitored by Anvil. If it fails in production,
# Anvil will automatically attempt to repair it.
# ═══════════════════════════════════════════════════════════════════════════════

{original_code}
'''

    def __init__(
        self,
        source_dir: str | Path,
        managed_dir: str | Path | None = None,
        manifest_file: str | Path | None = None,
    ):
        """Initialize the ingester.

        Args:
            source_dir: Directory containing tools to ingest
            managed_dir: Directory to store managed copies (default: ./anvil_managed)
            manifest_file: Path to manifest file (default: ./anvil_manifest.json)
        """
        self.source_dir = Path(source_dir)
        self.managed_dir = Path(managed_dir) if managed_dir else Path("./anvil_managed")
        self.manifest_file = Path(manifest_file) if manifest_file else Path("./anvil_manifest.json")
        self.analyzer = ToolAnalyzer()

    def scan(self) -> list[ToolInfo]:
        """Scan source directory for Python tools.

        Returns:
            List of ToolInfo objects for each discovered tool
        """
        tools = []

        if not self.source_dir.exists():
            return tools

        for py_file in sorted(self.source_dir.glob("*.py")):
            # Skip private/internal files
            if py_file.name.startswith("_"):
                continue

            tool = self.analyzer.analyze(py_file)
            tools.append(tool)

        return tools

    def wrap_tool(self, tool: ToolInfo) -> Path:
        """Copy tool to managed directory with Anvil wrapper.

        Args:
            tool: ToolInfo for the tool to wrap

        Returns:
            Path to the wrapped tool file
        """
        self.managed_dir.mkdir(parents=True, exist_ok=True)

        dest_path = self.managed_dir / f"{tool.name}.py"
        original_code = tool.source_file.read_text()

        wrapped_code = self.WRAPPER_TEMPLATE.format(
            source_file=tool.source_file,
            timestamp=datetime.now().isoformat(),
            original_code=original_code,
        )

        dest_path.write_text(wrapped_code)
        return dest_path

    def scan_and_register(self, wrap: bool = True) -> IngestManifest:
        """Scan tools and register them in a manifest.

        Args:
            wrap: If True, copy tools to managed directory with wrappers

        Returns:
            IngestManifest with all registered tools
        """
        tools = self.scan()

        manifest = IngestManifest(
            source_dir=str(self.source_dir),
            managed_dir=str(self.managed_dir),
        )

        for tool in tools:
            tool_entry = {
                "name": tool.name,
                "source_file": str(tool.source_file),
                "description": tool.description,
                "has_run_function": tool.has_run_function,
                "parameters": tool.parameters,
                "imports": tool.imports,
                "status": tool.status,
                "error": tool.error,
                "last_check": None,
            }

            if wrap:
                managed_path = self.wrap_tool(tool)
                tool_entry["managed_file"] = str(managed_path)

            manifest.tools.append(tool_entry)

        # Create __init__.py in managed directory
        if wrap:
            init_file = self.managed_dir / "__init__.py"
            if not init_file.exists():
                init_file.write_text('"""Anvil-managed tools."""\n')

            # Create tool registry
            registry_file = self.managed_dir / "tool_registry.json"
            registry = {
                t["name"]: {
                    "status": t["status"],
                    "source": t["source_file"],
                    "ingested": datetime.now().isoformat(),
                }
                for t in manifest.tools
            }
            registry_file.write_text(json.dumps(registry, indent=2))

        # Save manifest
        manifest.save(self.manifest_file)

        return manifest

    def update_tool_status(
        self,
        tool_name: str,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update a tool's status in the manifest.

        Args:
            tool_name: Name of the tool to update
            status: New status (pending, healthy, broken, repairing)
            error: Error message if status is broken
        """
        if not self.manifest_file.exists():
            return

        manifest = IngestManifest.load(self.manifest_file)

        for tool in manifest.tools:
            if tool["name"] == tool_name:
                tool["status"] = status
                tool["error"] = error
                tool["last_check"] = datetime.now().isoformat()
                break

        manifest.save(self.manifest_file)
