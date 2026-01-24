"""Anvil CLI - Command-line interface for managing Anvil tools.

Commands:
    anvil init      - Initialize a new Anvil project with interactive setup
    anvil ingest    - Scan and register existing tools for Anvil management
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
from anvil.sandbox import DockerSandbox, SecurityPolicy

# Try to import rich for beautiful output, fallback to basic if not available
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.prompt import Prompt
    from rich.table import Table
    from rich.text import Text
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# Initialize rich console
console = Console() if RICH_AVAILABLE else None


def print_welcome_banner() -> None:
    """Print a beautiful welcome banner using rich."""
    if RICH_AVAILABLE and console:
        banner_text = Text()
        banner_text.append("🔧 ", style="bold")
        banner_text.append("Anvil SDK", style="bold cyan")
        banner_text.append(" v" + __version__, style="dim")

        subtitle = Text("JIT Infrastructure & Self-Healing SDK for AI Agents", style="italic")

        console.print()
        console.print(Panel.fit(
            Text.assemble(banner_text, "\n", subtitle),
            border_style="cyan",
            padding=(1, 4),
        ))
        console.print()
    else:
        click.echo(f"\n🔧 Anvil SDK v{__version__}")
        click.echo("JIT Infrastructure & Self-Healing SDK for AI Agents\n")


def success(msg: str) -> None:
    """Print a success message."""
    if RICH_AVAILABLE and console:
        console.print(f"[green]✓[/green] {msg}")
    else:
        click.echo(f"✓ {msg}")


def warning(msg: str) -> None:
    """Print a warning message."""
    if RICH_AVAILABLE and console:
        console.print(f"[yellow]⚠[/yellow] {msg}")
    else:
        click.echo(f"⚠ {msg}")


def error(msg: str) -> None:
    """Print an error message."""
    if RICH_AVAILABLE and console:
        console.print(f"[red]✗[/red] {msg}")
    else:
        click.echo(f"✗ {msg}")


def info(msg: str) -> None:
    """Print an info message."""
    if RICH_AVAILABLE and console:
        console.print(f"[blue]ℹ[/blue] {msg}")
    else:
        click.echo(f"ℹ {msg}")


def header(msg: str) -> None:
    """Print a header message."""
    if RICH_AVAILABLE and console:
        console.print(f"[bold cyan]{msg}[/bold cyan]")
    else:
        click.echo(msg)


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
@click.option(
    "--skip-keys",
    is_flag=True,
    help="Skip API key setup (just create directory structure)",
)
def init(dir: str, tools_dir: str, force: bool, skip_keys: bool) -> None:
    """Initialize a new Anvil project with interactive setup.

    Creates the necessary directory structure, configuration files,
    and optionally sets up API keys interactively.
    """
    project_dir = Path(dir).resolve()

    # Print welcome banner
    print_welcome_banner()

    if RICH_AVAILABLE and console:
        console.print(f"[dim]Directory:[/dim] {project_dir}")
        console.print(f"[dim]Tools dir:[/dim] {tools_dir}")
        console.print()
    else:
        click.echo(f"Directory: {project_dir}")
        click.echo(f"Tools dir: {tools_dir}\n")

    # Step 1: Create tools directory
    header("📁 Setting up directory structure...")
    console.print() if RICH_AVAILABLE and console else None

    tools_path = project_dir / tools_dir
    if tools_path.exists() and not force:
        warning(f"Tools directory already exists: {tools_path}")
    else:
        tools_path.mkdir(parents=True, exist_ok=True)
        (tools_path / "__init__.py").write_text('"""Anvil-generated tools."""\n')
        (tools_path / "tool_registry.json").write_text("{}\n")
        success(f"Created tools directory: {tools_path}")

    # Step 2: Handle .gitignore
    header("🔒 Configuring security...")
    console.print() if RICH_AVAILABLE and console else None

    gitignore = project_dir / ".gitignore"
    gitignore_entries = [
        ".env",
        "__pycache__/",
        "*.pyc",
        f"{tools_dir}/__pycache__/",
    ]

    if gitignore.exists():
        existing = gitignore.read_text()
        # Check if .env is already in gitignore
        if ".env" not in existing:
            with open(gitignore, "a") as f:
                f.write("\n# Anvil - Protect API keys\n")
                f.write(".env\n")
            success("Added .env to .gitignore (protecting your API keys)")
        else:
            info(".env already in .gitignore")

        # Add other entries if missing
        new_entries = [e for e in gitignore_entries[1:] if e not in existing]
        if new_entries:
            with open(gitignore, "a") as f:
                if ".env" in existing:
                    f.write("\n# Anvil\n")
                f.write("\n".join(new_entries) + "\n")
    else:
        gitignore.write_text("# Anvil - Protect API keys\n" + "\n".join(gitignore_entries) + "\n")
        success(f"Created .gitignore with API key protection")

    # Step 3: Interactive API key setup
    env_file = project_dir / ".env"
    anthropic_key = ""
    firecrawl_key = ""

    # Check if we're in an interactive terminal
    is_interactive = sys.stdin.isatty() and sys.stdout.isatty()

    if not skip_keys and is_interactive:
        console.print() if RICH_AVAILABLE and console else click.echo()
        header("🔑 API Key Setup")
        console.print() if RICH_AVAILABLE and console else None

        if RICH_AVAILABLE and console:
            console.print("[dim]Your API keys will be stored locally in .env and never shared.[/dim]")
            console.print("[dim]Press Enter to skip any key you don't have yet.[/dim]")
            console.print()

            # Anthropic API Key
            console.print("[bold]Anthropic API Key[/bold] [dim](required for Claude)[/dim]")
            console.print("[dim]Get yours at: https://console.anthropic.com/settings/keys[/dim]")
            try:
                anthropic_key = Prompt.ask(
                    "  API Key",
                    password=True,
                    default="",
                    show_default=False,
                )
            except Exception:
                anthropic_key = ""
            console.print()

            # FireCrawl API Key
            console.print("[bold]FireCrawl API Key[/bold] [dim](optional, for doc fetching)[/dim]")
            console.print("[dim]Get yours at: https://www.firecrawl.dev/[/dim]")
            try:
                firecrawl_key = Prompt.ask(
                    "  API Key",
                    password=True,
                    default="",
                    show_default=False,
                )
            except Exception:
                firecrawl_key = ""
            console.print()
        else:
            click.echo("Your API keys will be stored locally in .env and never shared.")
            click.echo("Press Enter to skip any key you don't have yet.\n")

            click.echo("Anthropic API Key (required for Claude)")
            click.echo("Get yours at: https://console.anthropic.com/settings/keys")
            try:
                anthropic_key = click.prompt("  API Key", default="", hide_input=True, show_default=False)
            except Exception:
                anthropic_key = ""
            click.echo()

            click.echo("FireCrawl API Key (optional, for doc fetching)")
            click.echo("Get yours at: https://www.firecrawl.dev/")
            try:
                firecrawl_key = click.prompt("  API Key", default="", hide_input=True, show_default=False)
            except Exception:
                firecrawl_key = ""
            click.echo()

    # Step 4: Create .env file
    if env_file.exists() and not force:
        warning(f".env file already exists: {env_file}")
        if anthropic_key or firecrawl_key:
            info("To update keys, delete .env and run 'anvil init' again, or edit manually")
    else:
        env_content = f"""# Anvil Configuration
# Generated by 'anvil init'

# Anthropic API Key (for Claude)
# Get your key: https://console.anthropic.com/settings/keys
ANTHROPIC_API_KEY={anthropic_key}

# FireCrawl API Key (optional, for documentation fetching)
# Get your key: https://www.firecrawl.dev/
FIRECRAWL_API_KEY={firecrawl_key}
"""
        env_file.write_text(env_content)
        if anthropic_key:
            success("Created .env file with your API keys")
        else:
            success("Created .env file (add your API keys later)")

    # Step 5: Create example script
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
    )

    # Create a tool by defining its intent
    tool = anvil.use_tool(
        name="hello_world",
        intent="Print a greeting message that takes a name parameter",
    )

    # Run the tool
    result = tool.run(name="World")
    print(f"Result: {{result}}")

if __name__ == "__main__":
    main()
'''
        example_script.write_text(example_content)
        success(f"Created example script: {example_script}")

    # Final summary
    console.print() if RICH_AVAILABLE and console else click.echo()

    if RICH_AVAILABLE and console:
        # Create a nice summary panel
        next_steps = Text()
        next_steps.append("Next Steps:\n\n", style="bold")

        step_num = 1
        if not anthropic_key:
            next_steps.append(f"  {step_num}. ", style="cyan")
            next_steps.append(f"Add your API key to {env_file}\n")
            step_num += 1

        next_steps.append(f"  {step_num}. ", style="cyan")
        next_steps.append("Run: ")
        next_steps.append("python example.py\n", style="bold green")
        step_num += 1

        next_steps.append(f"  {step_num}. ", style="cyan")
        next_steps.append(f"Check your generated tools in: {tools_path}\n")

        console.print(Panel(
            next_steps,
            title="[bold green]✨ Anvil project initialized![/bold green]",
            border_style="green",
            padding=(1, 2),
        ))
        console.print()
    else:
        click.echo("✨ Anvil project initialized!\n")
        click.echo("Next steps:")
        if not anthropic_key:
            click.echo(f"  1. Add your API key to {env_file}")
            click.echo(f"  2. Run: python example.py")
            click.echo(f"  3. Check your tools in: {tools_path}\n")
        else:
            click.echo(f"  1. Run: python example.py")
            click.echo(f"  2. Check your tools in: {tools_path}\n")


@cli.command()
@click.argument("source_dir", type=click.Path(exists=True))
@click.option(
    "--managed-dir", "-m",
    default="./anvil_managed",
    help="Directory to store managed tools (default: ./anvil_managed)",
)
@click.option(
    "--manifest", "-o",
    default="./anvil_manifest.json",
    help="Path to manifest file (default: ./anvil_manifest.json)",
)
@click.option(
    "--no-wrap",
    is_flag=True,
    help="Don't copy tools to managed directory (just analyze)",
)
@click.option(
    "--json", "as_json",
    is_flag=True,
    help="Output as JSON",
)
def ingest(source_dir: str, managed_dir: str, manifest: str, no_wrap: bool, as_json: bool) -> None:
    """Scan and register existing tools for Anvil management.

    Analyzes Python files in SOURCE_DIR, identifies tool functions,
    and registers them with Anvil for monitoring and self-healing.

    Example:
        anvil ingest ./my_agent/tools
        anvil ingest ./legacy_tools --managed-dir ./anvil_tools
    """
    from anvil.ingest import ToolIngester

    source_path = Path(source_dir)

    if as_json:
        # Silent JSON mode
        ingester = ToolIngester(
            source_dir=source_path,
            managed_dir=managed_dir,
            manifest_file=manifest,
        )
        result = ingester.scan_and_register(wrap=not no_wrap)
        click.echo(json.dumps(result.to_dict(), indent=2))
        return

    # Pretty output mode
    print_welcome_banner()

    if RICH_AVAILABLE and console:
        console.print(Panel.fit(
            "[bold blue]Tool Ingestion[/bold blue]\n"
            "[dim]Scanning for existing tools to manage[/dim]",
            border_style="blue",
        ))
        console.print()
        console.print(f"[dim]Source:[/dim] {source_path.resolve()}")
        console.print(f"[dim]Managed:[/dim] {Path(managed_dir).resolve()}")
        console.print()
    else:
        click.echo("Tool Ingestion")
        click.echo(f"Source: {source_path.resolve()}")
        click.echo(f"Managed: {Path(managed_dir).resolve()}\n")

    # Run ingestion
    header("Scanning for tools...")
    if RICH_AVAILABLE and console:
        console.print()

    ingester = ToolIngester(
        source_dir=source_path,
        managed_dir=managed_dir,
        manifest_file=manifest,
    )

    # First scan to show what we found
    tools = ingester.scan()

    if not tools:
        warning("No Python tools found in source directory.")
        info("Tools must have a run() function to be recognized.")
        return

    # Display discovered tools
    if RICH_AVAILABLE and console:
        table = Table(title=f"Discovered Tools ({len(tools)})", box=box.ROUNDED)
        table.add_column("Status", width=3, justify="center")
        table.add_column("Name", style="bold")
        table.add_column("Description", style="dim", max_width=40)
        table.add_column("Parameters", style="cyan")

        for tool in tools:
            if tool.has_run_function:
                status_icon = "[green]✓[/green]"
            else:
                status_icon = "[red]✗[/red]"

            desc = tool.description[:40] + "..." if len(tool.description) > 40 else tool.description
            params = ", ".join(tool.parameters) if tool.parameters else "-"

            table.add_row(status_icon, tool.name, desc or "[dim]No description[/dim]", params)

        console.print(table)
        console.print()
    else:
        click.echo(f"\nDiscovered Tools ({len(tools)}):\n")
        for tool in tools:
            status = "✓" if tool.has_run_function else "✗"
            click.echo(f"  {status} {tool.name}")
            if tool.description:
                click.echo(f"      {tool.description[:60]}")
        click.echo()

    # Register and wrap
    if no_wrap:
        info("Skipping wrap (--no-wrap flag set)")
        result = ingester.scan_and_register(wrap=False)
    else:
        header("Wrapping tools for Anvil management...")
        if RICH_AVAILABLE and console:
            console.print()

        result = ingester.scan_and_register(wrap=True)

        for tool in result.tools:
            if tool.get("managed_file"):
                success(f"{tool['name']} → {tool['managed_file']}")

    # Save manifest
    if RICH_AVAILABLE and console:
        console.print()
        console.print(f"[green]✓[/green] Manifest saved: {manifest}")
        console.print()

        # Summary panel
        stats = result.to_dict()["stats"]
        summary = Text()
        summary.append("Ingestion Complete\n\n", style="bold green")
        summary.append(f"  Total tools:  {stats['total']}\n")
        summary.append(f"  Ready:        {stats['pending']}\n")
        if stats['broken'] > 0:
            summary.append(f"  Broken:       {stats['broken']}\n", style="red")

        summary.append("\n")
        summary.append("Next steps:\n", style="bold")
        summary.append("  1. Review tools in: ", style="dim")
        summary.append(f"{managed_dir}\n", style="cyan")
        summary.append("  2. Run health checks with your agent\n", style="dim")

        console.print(Panel(summary, border_style="green"))
        console.print()
    else:
        stats = result.to_dict()["stats"]
        click.echo(f"\n✓ Manifest saved: {manifest}")
        click.echo(f"\nTotal: {stats['total']} | Ready: {stats['pending']} | Broken: {stats['broken']}\n")


@cli.command()
def doctor() -> None:
    """Check system requirements and configuration.

    Verifies that all dependencies are available and properly configured.
    """
    print_welcome_banner()
    header("🩺 System Health Check")
    console.print() if RICH_AVAILABLE and console else click.echo()

    all_ok = True

    if RICH_AVAILABLE and console:
        table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
        table.add_column("Status", width=3)
        table.add_column("Component", width=25)
        table.add_column("Details", style="dim")

        # Check Python version
        py_version = sys.version_info
        if py_version >= (3, 10):
            table.add_row("[green]✓[/green]", "Python", f"{py_version.major}.{py_version.minor}.{py_version.micro}")
        else:
            table.add_row("[red]✗[/red]", "Python", f"{py_version.major}.{py_version.minor} (need 3.10+)")
            all_ok = False

        # Check Docker
        docker_sandbox = DockerSandbox()
        if docker_sandbox.is_available():
            try:
                result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
                version = result.stdout.strip().replace("Docker version ", "")
                table.add_row("[green]✓[/green]", "Docker", version.split(",")[0])
            except Exception:
                table.add_row("[green]✓[/green]", "Docker", "available")
        else:
            table.add_row("[yellow]○[/yellow]", "Docker", "not found (optional)")

        # Check rich
        table.add_row("[green]✓[/green]", "Rich CLI", "enabled")

        console.print(table)
        console.print()

        # API Keys section
        header("🔑 API Keys")
        console.print()

        key_table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
        key_table.add_column("Status", width=3)
        key_table.add_column("Key", width=20)
        key_table.add_column("Value", style="dim")

        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            masked = anthropic_key[:8] + "..." + anthropic_key[-4:] if len(anthropic_key) > 12 else "***"
            key_table.add_row("[green]✓[/green]", "ANTHROPIC_API_KEY", masked)
        else:
            key_table.add_row("[red]✗[/red]", "ANTHROPIC_API_KEY", "not set")
            all_ok = False

        firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
        if firecrawl_key:
            masked = firecrawl_key[:8] + "..." + firecrawl_key[-4:] if len(firecrawl_key) > 12 else "***"
            key_table.add_row("[green]✓[/green]", "FIRECRAWL_API_KEY", masked)
        else:
            key_table.add_row("[yellow]○[/yellow]", "FIRECRAWL_API_KEY", "not set (optional)")

        console.print(key_table)
        console.print()

        # Configuration section
        header("📁 Configuration")
        console.print()

        config_table = Table(box=box.ROUNDED, show_header=False, padding=(0, 2))
        config_table.add_column("Status", width=3)
        config_table.add_column("Item", width=20)
        config_table.add_column("Path", style="dim")

        env_file = Path(".env")
        if env_file.exists():
            config_table.add_row("[green]✓[/green]", ".env file", str(env_file.resolve()))
        else:
            config_table.add_row("[yellow]○[/yellow]", ".env file", "run 'anvil init'")

        tools_dir = Path("anvil_tools")
        if tools_dir.exists():
            tool_count = len(list(tools_dir.glob("*.py"))) - 1
            config_table.add_row("[green]✓[/green]", "Tools directory", f"{tool_count} tools")
        else:
            config_table.add_row("[yellow]○[/yellow]", "Tools directory", "run 'anvil init'")

        console.print(config_table)
        console.print()

    else:
        # Fallback to basic output
        py_version = sys.version_info
        if py_version >= (3, 10):
            success(f"Python {py_version.major}.{py_version.minor}.{py_version.micro}")
        else:
            error(f"Python {py_version.major}.{py_version.minor} (need 3.10+)")
            all_ok = False

        docker_sandbox = DockerSandbox()
        if docker_sandbox.is_available():
            success("Docker available")
        else:
            warning("Docker not available (sandbox will use local execution)")

        click.echo("\nAPI Keys:")
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            masked = anthropic_key[:8] + "..." + anthropic_key[-4:] if len(anthropic_key) > 12 else "***"
            success(f"ANTHROPIC_API_KEY: {masked}")
        else:
            error("ANTHROPIC_API_KEY: Not set")
            all_ok = False

        firecrawl_key = os.environ.get("FIRECRAWL_API_KEY")
        if firecrawl_key:
            masked = firecrawl_key[:8] + "..." + firecrawl_key[-4:] if len(firecrawl_key) > 12 else "***"
            success(f"FIRECRAWL_API_KEY: {masked}")
        else:
            info("FIRECRAWL_API_KEY: Not set (optional)")

        click.echo("\nConfiguration:")
        env_file = Path(".env")
        if env_file.exists():
            success(f".env file found: {env_file.resolve()}")
        else:
            warning(".env file not found - run 'anvil init'")

        tools_dir = Path("anvil_tools")
        if tools_dir.exists():
            tool_count = len(list(tools_dir.glob("*.py"))) - 1
            success(f"Tools directory: {tools_dir.resolve()} ({tool_count} tools)")
        else:
            info("Tools directory not found - run 'anvil init'")

    # Summary
    if RICH_AVAILABLE and console:
        if all_ok:
            console.print(Panel("[bold green]All checks passed![/bold green]", border_style="green"))
        else:
            console.print(Panel("[bold yellow]Some issues found. See above for details.[/bold yellow]", border_style="yellow"))
        console.print()
    else:
        if all_ok:
            click.echo("\n✅ All checks passed!\n")
        else:
            click.echo("\n⚠️  Some issues found. See above for details.\n")


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
            error(f"Tools directory not found: {tools_dir}")
            info("Run 'anvil init' to create one")
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
        info("No tools found.")
        info("Use Anvil to generate tools with anvil.use_tool()")
        return

    if RICH_AVAILABLE and console:
        console.print()
        header(f"📦 Anvil Tools ({len(tools)} total)")
        console.print()

        table = Table(box=box.ROUNDED, padding=(0, 1))
        table.add_column("Status", width=3, justify="center")
        table.add_column("Name", style="bold")
        table.add_column("Version", style="dim")
        table.add_column("Intent", style="cyan", max_width=50)

        for tool in tools:
            version = tool.get("version", "?")
            status = tool.get("status", "unknown")
            intent = tool.get("intent", "")

            if len(intent) > 50:
                intent = intent[:47] + "..."

            if status == "active":
                status_icon = "[green]●[/green]"
            elif status == "failed":
                status_icon = "[red]●[/red]"
            elif status == "ejected":
                status_icon = "[yellow]●[/yellow]"
            else:
                status_icon = "○"

            table.add_row(status_icon, tool["name"], f"v{version}", intent)

        console.print(table)
        console.print()
    else:
        click.echo(f"\n📦 Anvil Tools ({len(tools)} total)\n")
        for tool in tools:
            version = tool.get("version", "?")
            status = tool.get("status", "unknown")
            intent = tool.get("intent", "")

            if status == "active":
                status_icon = "●"
            elif status == "failed":
                status_icon = "✗"
            elif status == "ejected":
                status_icon = "○"
            else:
                status_icon = "?"

            click.echo(f"  {status_icon} {tool['name']} (v{version})")
            if intent:
                display_intent = intent[:60] + "..." if len(intent) > 60 else intent
                click.echo(f"      {display_intent}")
        click.echo()


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
        error(f"Tools directory not found: {tools_dir}")
        return

    tool_files = list(tools_dir.glob("*.py"))
    tool_files = [f for f in tool_files if f.name != "__init__.py"]

    if not tool_files:
        info("No tools to clean.")
        return

    registry_file = tools_dir / "tool_registry.json"
    registry: dict[str, Any] = {}
    if registry_file.exists():
        try:
            registry = json.loads(registry_file.read_text())
        except json.JSONDecodeError:
            pass

    ejected_tools = []
    managed_tools = []

    for path in tool_files:
        tool_name = path.stem
        meta = registry.get(tool_name, {})
        if meta.get("status") == "ejected" or _is_ejected(path):
            ejected_tools.append(path)
        else:
            managed_tools.append(path)

    if RICH_AVAILABLE and console:
        console.print()
        header("🧹 Anvil Clean")
        console.print()

        if managed_tools:
            console.print(f"  Managed tools to remove: [bold]{len(managed_tools)}[/bold]")
            for path in managed_tools[:5]:
                console.print(f"    [dim]-[/dim] {path.stem}")
            if len(managed_tools) > 5:
                console.print(f"    [dim]... and {len(managed_tools) - 5} more[/dim]")

        if ejected_tools:
            if keep_ejected:
                console.print(f"  Ejected tools (keeping): [yellow]{len(ejected_tools)}[/yellow]")
            else:
                console.print(f"  Ejected tools to remove: [yellow]{len(ejected_tools)}[/yellow]")

        console.print()
    else:
        click.echo("\n🧹 Anvil Clean\n")
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
        click.echo()

    if not force:
        if not click.confirm("Proceed with cleanup?"):
            click.echo("Cancelled.")
            return

    deleted = 0
    for path in managed_tools:
        path.unlink()
        deleted += 1
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

    registry_file.write_text(json.dumps(registry, indent=2))

    pycache = tools_dir / "__pycache__"
    if pycache.exists():
        shutil.rmtree(pycache)

    success(f"Removed {deleted} tools.")
    info("Tools will be regenerated on next use.\n")


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
        error(f"Tool not found: {tool_path}")
        return

    if RICH_AVAILABLE and console:
        console.print()
        header(f"🔍 Verifying: {tool_name}")
        console.print()
    else:
        click.echo(f"\n🔍 Verifying: {tool_name}\n")

    code = tool_path.read_text()

    lines = code.split("\n")
    code_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# ---"):
            code_start = i + 1
            break
    if code_start > 0:
        code = "\n".join(lines[code_start:])

    from anvil.sandbox import SandboxManager

    sandbox = SandboxManager(
        policy=SecurityPolicy(allow_network=True),
        prefer_docker=True,
    )

    info(f"Sandbox: {sandbox.get_status()['active_driver']}")
    console.print() if RICH_AVAILABLE and console else click.echo()

    result = sandbox.verify_code(code)

    if result.success:
        success("Code passed verification!")
        if result.output:
            if RICH_AVAILABLE and console:
                console.print(Panel(result.output[:500], title="Output", border_style="dim"))
            else:
                click.echo(f"\n  Output:\n{result.output[:500]}")
        info(f"Duration: {result.duration_ms:.1f}ms")
    else:
        error("Code failed verification!")
        if RICH_AVAILABLE and console:
            console.print(f"\n  [red]Error:[/red] {result.error}")
        else:
            click.echo(f"\n  Error: {result.error}")
        if result.security_violations:
            click.echo("\n  Security violations:")
            for v in result.security_violations:
                click.echo(f"    - {v}")

    console.print() if RICH_AVAILABLE and console else click.echo()


def _is_ejected(path: Path) -> bool:
    """Check if a tool file is ejected (user-controlled)."""
    try:
        content = path.read_text()
        for line in content.split("\n")[:10]:
            if "ANVIL-MANAGED: false" in line:
                return True
            if "ANVIL-MANAGED: true" in line:
                return False
        return True
    except Exception:
        return False


def main() -> None:
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
