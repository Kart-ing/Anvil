#!/usr/bin/env python3
"""Anvil Enterprise - Tool Ingestion Script.

Scans a legacy agent's tool folder and registers tools with Anvil.
Creates a manifest for the dashboard and wraps tools for management.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# Directories
AGENT_TOOLS_DIR = Path("my_agent/tools")
MANAGED_DIR = Path("anvil_managed")
MANIFEST_FILE = Path("anvil_manifest.json")


def scan_tools(tools_dir: Path) -> list[dict]:
    """Scan directory for Python tool files."""
    tools = []

    for py_file in tools_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue

        tool_name = py_file.stem
        code = py_file.read_text()

        # Extract docstring for description
        description = "No description"
        if '"""' in code:
            start = code.find('"""') + 3
            end = code.find('"""', start)
            if end > start:
                description = code[start:end].strip().split("\n")[0]

        tools.append({
            "name": tool_name,
            "source_file": str(py_file),
            "description": description,
            "status": "pending",  # pending, healthy, broken, repairing
            "last_check": None,
            "error": None,
        })

    return tools


def wrap_tool(source_path: Path, dest_dir: Path) -> Path:
    """Copy tool to managed directory with Anvil wrapper."""
    dest_path = dest_dir / source_path.name

    # Read original code
    original_code = source_path.read_text()

    # Add Anvil management header
    wrapped_code = f'''# ANVIL MANAGED TOOL
# Original: {source_path}
# Wrapped: {datetime.now().isoformat()}
# Status: managed
#
# This tool is monitored by Anvil Enterprise.
# If it fails, Anvil will automatically repair it.

{original_code}
'''

    dest_path.write_text(wrapped_code)
    return dest_path


def create_manifest(tools: list[dict]) -> dict:
    """Create the Anvil manifest file."""
    manifest = {
        "version": "1.0",
        "created": datetime.now().isoformat(),
        "agent": {
            "name": "my_agent",
            "tools_dir": str(AGENT_TOOLS_DIR),
            "managed_dir": str(MANAGED_DIR),
        },
        "tools": tools,
        "stats": {
            "total": len(tools),
            "healthy": 0,
            "broken": 0,
            "repairing": 0,
        },
    }
    return manifest


def main():
    """Run the ingestion process."""
    console.print(Panel.fit(
        "[bold blue]ANVIL ENTERPRISE[/bold blue]\n"
        "[dim]Tool Ingestion System[/dim]",
        border_style="blue",
    ))

    # Check source directory
    if not AGENT_TOOLS_DIR.exists():
        console.print(f"[red]Error:[/red] Tools directory not found: {AGENT_TOOLS_DIR}")
        return

    # Create managed directory
    MANAGED_DIR.mkdir(exist_ok=True)

    # Scan for tools
    console.print("\n[bold]Scanning for tools...[/bold]")
    tools = scan_tools(AGENT_TOOLS_DIR)

    if not tools:
        console.print("[yellow]No tools found.[/yellow]")
        return

    # Display found tools
    table = Table(title="Discovered Tools")
    table.add_column("Tool Name", style="cyan")
    table.add_column("Description", style="dim")
    table.add_column("Status", style="yellow")

    for tool in tools:
        table.add_row(tool["name"], tool["description"], "pending")

    console.print(table)

    # Wrap tools
    console.print("\n[bold]Wrapping tools for Anvil management...[/bold]")
    for tool in tools:
        source = Path(tool["source_file"])
        dest = wrap_tool(source, MANAGED_DIR)
        tool["managed_file"] = str(dest)
        console.print(f"  [green]✓[/green] {tool['name']} → {dest}")

    # Create manifest
    manifest = create_manifest(tools)
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2))
    console.print(f"\n[green]✓[/green] Manifest created: {MANIFEST_FILE}")

    # Summary
    console.print(Panel.fit(
        f"[bold green]Ingestion Complete[/bold green]\n\n"
        f"Tools registered: {len(tools)}\n"
        f"Managed directory: {MANAGED_DIR}\n"
        f"Manifest: {MANIFEST_FILE}\n\n"
        f"[dim]Run 'streamlit run dashboard.py' to monitor[/dim]",
        border_style="green",
    ))


if __name__ == "__main__":
    main()
