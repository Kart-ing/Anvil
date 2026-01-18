"""Anvil CLI - Command-line interface for managing Anvil tools.

Commands:
    anvil init      - Initialize a new Anvil project
    anvil doctor    - Check system requirements and configuration
    anvil list      - List all cached tools
    anvil clean     - Clear the tool cache
    anvil run       - Run a tool interactively
    anvil verify    - Verify a tool's code in sandbox
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from anvil import Anvil, __version__
from anvil.sandbox import DockerSandbox, LocalSandbox, SecurityPolicy


# ANSI color codes for pretty output
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    END = "\033[0m"


def success(msg: str) -> str:
    return f"{Colors.GREEN}✓{Colors.END} {msg}"


def warning(msg: str) -> str:
    return f"{Colors.YELLOW}⚠{Colors.END} {msg}"


def error(msg: str) -> str:
    return f"{Colors.RED}✗{Colors.END} {msg}"


def info(msg: str) -> str:
    return f"{Colors.BLUE}ℹ{Colors.END} {msg}"


def header(msg: str) -> str:
    return f"{Colors.BOLD}{Colors.CYAN}{msg}{Colors.END}"


@click.group()
@click.version_option(version=__version__, prog_name="anvil")
def cli() -> None:
    """Anvil - JIT Infrastructure & Self-Healing SDK for AI Agents.

    Generate, manage, and execute tools with automatic code generation
    and self-healing capabilities.
    """
    pass


@cli.command()
@click.option(
    "--dir", "-d",
    default=".",
    help="Directory to initialize (default: current directory)",
)
@click.option(
    "--tools-dir",
    default="anvil_tools",
    help="Name of the tools directory (default: anvil_tools)",
)
@click.option(
    "--force", "-f",
    is_flag=True,
    help="Overwrite existing files",
)
def init(dir: str, tools_dir: str, force: bool) -> None:
    """Initialize a new Anvil project.

    Creates the necessary directory structure and configuration files.
    """
    project_dir = Path(dir).resolve()

    click.echo(header("\n🔧 Initializing Anvil Project\n"))
    click.echo(f"   Directory: {project_dir}")
    click.echo(f"   Tools dir: {tools_dir}\n")

    # Create tools directory
    tools_path = project_dir / tools_dir
    if tools_path.exists() and not force:
        click.echo(warning(f"Tools directory already exists: {tools_path}"))
    else:
        tools_path.mkdir(parents=True, exist_ok=True)
        (tools_path / "__init__.py").write_text('"""Anvil-generated tools."""\n')
        (tools_path / "tool_registry.json").write_text("{}\n")
        click.echo(success(f"Created tools directory: {tools_path}"))

    # Create .env file if it doesn't exist
    env_file = project_dir / ".env"
    if env_file.exists() and not force:
        click.echo(warning(f".env file already exists: {env_file}"))
    else:
        env_content = """# Anvil Configuration
# Get your Anthropic API key from: https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY=

# Optional: FireCrawl API key for documentation fetching
# Get your key from: https://www.firecrawl.dev/
FIRECRAWL_API_KEY=
"""
        env_file.write_text(env_content)
        click.echo(success(f"Created .env file: {env_file}"))

    # Create .gitignore entries
    gitignore = project_dir / ".gitignore"
    gitignore_entries = [
        ".env",
        "__pycache__/",
        "*.pyc",
        f"{tools_dir}/__pycache__/",
    ]

    if gitignore.exists():
        existing = gitignore.read_text()
        new_entries = [e for e in gitignore_entries if e not in existing]
        if new_entries:
            with open(gitignore, "a") as f:
                f.write("\n# Anvil\n")
                f.write("\n".join(new_entries) + "\n")
            click.echo(success("Updated .gitignore"))
        else:
            click.echo(info(".gitignore already configured"))
    else:
        gitignore.write_text("# Anvil\n" + "\n".join(gitignore_entries) + "\n")
        click.echo(success(f"Created .gitignore: {gitignore}"))

    # Create example script
    example_script = project_dir / "example.py"
    if not example_script.exists() or force:
        example_content = f'''"""Example Anvil usage."""
from dotenv import load_dotenv
from anvil import Anvil

load_dotenv()

def main():
    # Initialize Anvil
    anvil = Anvil(
        tools_dir="./{tools_dir}",
        self_healing=True,
        interactive_credentials=True,
        verified_mode=False,  # Set to True to enable sandbox verification
    )

    # Create a tool by defining its intent
    tool = anvil.use_tool(
        name="hello_world",
        intent="Print a greeting message",
    )

    # Run the tool
    result = tool.run(name="World")
    print(f"Result: {{result}}")

if __name__ == "__main__":
    main()
'''
        example_script.write_text(example_content)
        click.echo(success(f"Created example script: {example_script}"))

    click.echo(header("\n✨ Anvil project initialized!\n"))
    click.echo("Next steps:")
    click.echo(f"  1. Add your API key to {env_file}")
    click.echo(f"  2. Run: python example.py")
    click.echo(f"  3. Check your tools in: {tools_path}\n")


@cli.command()
def doctor() -> None:
    """Check system requirements and configuration.

    Verifies that all dependencies are available and properly configured.
    """
    click.echo(header("\n🩺 Anvil Doctor - System Check\n"))

    all_ok = True

    # Check Python version
    py_version = sys.version_info
    if py_version >= (3, 10):
        click.echo(success(f"Python {py_version.major}.{py_version.minor}.{py_version.micro}"))
    else:
        click.echo(error(f"Python {py_version.major}.{py_version.minor} (need 3.10+)"))
        all_ok = False

    # Check Docker
    docker_sandbox = DockerSandbox()
    if docker_sandbox.is_available():
        # Get Docker version
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
            )
            version = result.stdout.strip()
            click.echo(success(f"Docker available: {version}"))
        except Exception:
            click.echo(success("Docker available"))
    else:
        click.echo(warning("Docker not available (sandbox will use local execution)"))

    # Check API keys
    click.echo("")
    click.echo(header("API Keys:"))

    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        # Mask the key
        masked = anthropic_key[:8] + "..." + anthropic_key[-4:] if len(anthropic_key) > 12 else "***"
        click.echo(success(f"ANTHROPIC_API_KEY: {masked}"))
    else:
        click.echo(error("ANTHROPIC_API_KEY: Not set"))
        click.echo(info("  Get your key: https://console.anthropic.com/settings/keys"))
        all_ok = False

    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
    if firecrawl_key:
        masked = firecrawl_key[:8] + "..." + firecrawl_key[-4:] if len(firecrawl_key) > 12 else "***"
        click.echo(success(f"FIRECRAWL_API_KEY: {masked}"))
    else:
        click.echo(info("FIRECRAWL_API_KEY: Not set (optional)"))
        click.echo(info("  Get your key: https://www.firecrawl.dev/"))

    # Check for .env file
    click.echo("")
    click.echo(header("Configuration:"))

    env_file = Path(".env")
    if env_file.exists():
        click.echo(success(f".env file found: {env_file.resolve()}"))
    else:
        click.echo(warning(".env file not found"))
        click.echo(info("  Run 'anvil init' to create one"))

    # Check tools directory
    tools_dir = Path("anvil_tools")
    if tools_dir.exists():
        tool_count = len(list(tools_dir.glob("*.py"))) - 1  # Exclude __init__.py
        click.echo(success(f"Tools directory: {tools_dir.resolve()} ({tool_count} tools)"))
    else:
        click.echo(info("Tools directory not found"))
        click.echo(info("  Run 'anvil init' to create one"))

    # Summary
    click.echo("")
    if all_ok:
        click.echo(header("✅ All checks passed!\n"))
    else:
        click.echo(header("⚠️  Some issues found. See above for details.\n"))


@cli.command("list")
@click.option(
    "--dir", "-d",
    default="./anvil_tools",
    help="Tools directory (default: ./anvil_tools)",
)
@click.option(
    "--json", "as_json",
    is_flag=True,
    help="Output as JSON",
)
def list_tools(dir: str, as_json: bool) -> None:
    """List all cached tools and their versions."""
    tools_dir = Path(dir)

    if not tools_dir.exists():
        if as_json:
            click.echo(json.dumps({"error": "Tools directory not found", "tools": []}))
        else:
            click.echo(error(f"Tools directory not found: {tools_dir}"))
            click.echo(info("Run 'anvil init' to create one"))
        return

    # Load registry
    registry_file = tools_dir / "tool_registry.json"
    registry: dict[str, Any] = {}
    if registry_file.exists():
        try:
            registry = json.loads(registry_file.read_text())
        except json.JSONDecodeError:
            pass

    # Find all tools
    tools = []
    for path in sorted(tools_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue

        tool_name = path.stem
        tool_info: dict[str, Any] = {
            "name": tool_name,
            "file": str(path),
            "size_bytes": path.stat().st_size,
            "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
        }

        # Add registry info if available
        if tool_name in registry:
            meta = registry[tool_name]
            tool_info.update({
                "version": meta.get("version", "unknown"),
                "intent": meta.get("intent", ""),
                "status": meta.get("status", "unknown"),
            })

        tools.append(tool_info)

    if as_json:
        click.echo(json.dumps({"tools": tools}, indent=2))
        return

    if not tools:
        click.echo(info("No tools found."))
        click.echo(info("Use Anvil to generate tools with anvil.use_tool()"))
        return

    click.echo(header(f"\n📦 Anvil Tools ({len(tools)} total)\n"))

    for tool in tools:
        version = tool.get("version", "?")
        status = tool.get("status", "unknown")
        intent = tool.get("intent", "")

        # Status indicator
        if status == "active":
            status_icon = Colors.GREEN + "●" + Colors.END
        elif status == "failed":
            status_icon = Colors.RED + "●" + Colors.END
        elif status == "ejected":
            status_icon = Colors.YELLOW + "●" + Colors.END
        else:
            status_icon = "○"

        click.echo(f"  {status_icon} {Colors.BOLD}{tool['name']}{Colors.END} (v{version})")
        if intent:
            # Truncate long intents
            display_intent = intent[:60] + "..." if len(intent) > 60 else intent
            click.echo(f"      {Colors.CYAN}{display_intent}{Colors.END}")

    click.echo("")


@cli.command()
@click.option(
    "--dir", "-d",
    default="./anvil_tools",
    help="Tools directory (default: ./anvil_tools)",
)
@click.option(
    "--force", "-f",
    is_flag=True,
    help="Skip confirmation prompt",
)
@click.option(
    "--keep-ejected",
    is_flag=True,
    help="Keep tools marked as ejected (user-controlled)",
)
def clean(dir: str, force: bool, keep_ejected: bool) -> None:
    """Clear the tool cache to force regeneration.

    This removes all generated tools from the cache directory.
    Tools will be regenerated on next use.
    """
    tools_dir = Path(dir)

    if not tools_dir.exists():
        click.echo(error(f"Tools directory not found: {tools_dir}"))
        return

    # Count tools
    tool_files = list(tools_dir.glob("*.py"))
    tool_files = [f for f in tool_files if f.name != "__init__.py"]

    if not tool_files:
        click.echo(info("No tools to clean."))
        return

    # Load registry to check for ejected tools
    registry_file = tools_dir / "tool_registry.json"
    registry: dict[str, Any] = {}
    if registry_file.exists():
        try:
            registry = json.loads(registry_file.read_text())
        except json.JSONDecodeError:
            pass

    # Separate ejected and managed tools
    ejected_tools = []
    managed_tools = []

    for path in tool_files:
        tool_name = path.stem
        meta = registry.get(tool_name, {})
        if meta.get("status") == "ejected" or _is_ejected(path):
            ejected_tools.append(path)
        else:
            managed_tools.append(path)

    # Show what will be deleted
    click.echo(header("\n🧹 Anvil Clean\n"))

    if managed_tools:
        click.echo(f"  Managed tools to remove: {len(managed_tools)}")
        for path in managed_tools[:5]:
            click.echo(f"    - {path.stem}")
        if len(managed_tools) > 5:
            click.echo(f"    ... and {len(managed_tools) - 5} more")

    if ejected_tools:
        if keep_ejected:
            click.echo(f"  Ejected tools (keeping): {len(ejected_tools)}")
        else:
            click.echo(f"  Ejected tools to remove: {len(ejected_tools)}")

    click.echo("")

    # Confirm
    if not force:
        if not click.confirm("Proceed with cleanup?"):
            click.echo("Cancelled.")
            return

    # Delete tools
    deleted = 0
    for path in managed_tools:
        path.unlink()
        deleted += 1
        # Remove from registry
        tool_name = path.stem
        if tool_name in registry:
            del registry[tool_name]

    if not keep_ejected:
        for path in ejected_tools:
            path.unlink()
            deleted += 1
            tool_name = path.stem
            if tool_name in registry:
                del registry[tool_name]

    # Update registry
    registry_file.write_text(json.dumps(registry, indent=2))

    # Clean up __pycache__
    pycache = tools_dir / "__pycache__"
    if pycache.exists():
        shutil.rmtree(pycache)

    click.echo(success(f"Removed {deleted} tools."))
    click.echo(info("Tools will be regenerated on next use.\n"))


@cli.command()
@click.argument("tool_name")
@click.option(
    "--dir", "-d",
    default="./anvil_tools",
    help="Tools directory (default: ./anvil_tools)",
)
def verify(tool_name: str, dir: str) -> None:
    """Verify a tool's code in the sandbox.

    Runs static analysis and optional sandbox execution to check
    if the tool code is safe.
    """
    tools_dir = Path(dir)
    tool_path = tools_dir / f"{tool_name}.py"

    if not tool_path.exists():
        click.echo(error(f"Tool not found: {tool_path}"))
        return

    click.echo(header(f"\n🔍 Verifying: {tool_name}\n"))

    # Read the code
    code = tool_path.read_text()

    # Strip header if present
    lines = code.split("\n")
    code_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# ---"):
            code_start = i + 1
            break
    if code_start > 0:
        code = "\n".join(lines[code_start:])

    # Create sandbox and verify
    from anvil.sandbox import SandboxManager

    sandbox = SandboxManager(
        policy=SecurityPolicy(allow_network=True),  # Allow network for API calls
        prefer_docker=True,
    )

    click.echo(f"  Sandbox: {sandbox.get_status()['active_driver']}")
    click.echo("")

    result = sandbox.verify_code(code)

    if result.success:
        click.echo(success("Code passed verification!"))
        if result.output:
            click.echo(f"\n  Output:\n{result.output[:500]}")
        click.echo(f"\n  Duration: {result.duration_ms:.1f}ms")
    else:
        click.echo(error("Code failed verification!"))
        click.echo(f"\n  Error: {result.error}")
        if result.security_violations:
            click.echo("\n  Security violations:")
            for v in result.security_violations:
                click.echo(f"    - {v}")

    click.echo("")


def _is_ejected(path: Path) -> bool:
    """Check if a tool file is ejected (user-controlled)."""
    try:
        content = path.read_text()
        # Check first few lines for header
        for line in content.split("\n")[:10]:
            if "ANVIL-MANAGED: false" in line:
                return True
            if "ANVIL-MANAGED: true" in line:
                return False
        # No header = ejected
        return True
    except Exception:
        return False


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
