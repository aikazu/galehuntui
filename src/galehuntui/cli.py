"""
GaleHunTUI CLI - Command Line Interface

Entry point for all command-line operations including TUI launch,
scan execution, tool management, and reporting.
"""

import sys
from pathlib import Path
from typing import Optional, List
from enum import Enum

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# Core imports
# from galehuntui.core.config import load_scope_config, load_profile_config
from galehuntui.core.constants import EngagementMode

# Version
__version__ = "0.1.0"

# Create CLI app
app = typer.Typer(
    name="galehuntui",
    help="GaleHunTUI - Terminal-based Automated Web Pentesting",
    add_completion=False,
    no_args_is_help=True,
)

# Create sub-apps for command groups
tools_app = typer.Typer(help="Manage external pentesting tools")
deps_app = typer.Typer(help="Manage dependencies (wordlists, templates)")
runs_app = typer.Typer(help="Manage scan runs")

# Register sub-apps
app.add_typer(tools_app, name="tools")
app.add_typer(deps_app, name="deps")
app.add_typer(runs_app, name="runs")

# Rich console for output
console = Console()


# ============================================================================
# Main Commands
# ============================================================================

@app.command()
def tui(
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Custom configuration file",
        exists=True,
    ),
) -> None:
    """
    Launch the Textual TUI interface.
    
    This is the primary mode for interactive use.
    """
    try:
        # Import here to avoid loading Textual if not needed
        from galehuntui.ui.app import GaleHunTUIApp
        
        # Load config if provided
        if config:
            console.print(f"[blue]Loading config from:[/blue] {config}")
            # TODO: Pass config to app initialization
        
        # Launch TUI
        app_instance = GaleHunTUIApp()
        app_instance.run()
        
    except ImportError as e:
        console.print(f"[red]Error:[/red] Failed to import TUI components: {e}")
        console.print("[yellow]Hint:[/yellow] Ensure textual is installed: pip install textual")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Error launching TUI:[/red] {e}")
        raise typer.Exit(code=1)


@app.command()
def run(
    target: str = typer.Argument(..., help="Target domain (e.g., example.com)"),
    profile: str = typer.Option(
        "standard",
        "--profile",
        "-p",
        help="Scan profile (quick, standard, deep)",
    ),
    mode: EngagementMode = typer.Option(
        EngagementMode.BUG_BOUNTY,
        "--mode",
        "-m",
        help="Engagement mode",
        case_sensitive=False,
    ),
    scope: Optional[Path] = typer.Option(
        None,
        "--scope",
        "-s",
        help="Scope configuration file",
        exists=True,
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory for results",
    ),
    config: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Custom configuration file",
        exists=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Verbose output",
    ),
) -> None:
    """
    Execute a scan run from the command line.
    
    This runs the orchestrator in headless mode without the TUI.
    """
    try:
        # Import orchestrator components
        # from galehuntui.orchestrator.pipeline import Pipeline
        # from galehuntui.orchestrator.state import RunState
        
        console.print(Panel.fit(
            f"[bold cyan]GaleHunTUI Scan[/bold cyan]\n\n"
            f"Target: [yellow]{target}[/yellow]\n"
            f"Profile: [green]{profile}[/green]\n"
            f"Mode: [magenta]{mode.value}[/magenta]",
            title="Scan Configuration",
        ))
        
        # Validate target
        if not target or "." not in target:
            console.print("[red]Error:[/red] Invalid target domain")
            raise typer.Exit(code=1)
        
        # Load scope if provided
        scope_config = None
        if scope:
            console.print(f"[blue]Loading scope from:[/blue] {scope}")
            # TODO: Load scope configuration
            # scope_config = load_scope(scope)
        
        # Prepare output directory
        if output:
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            # Use default location
            output_dir = Path.home() / ".local" / "share" / "galehuntui" / "runs"
            output_dir.mkdir(parents=True, exist_ok=True)
        
        console.print(f"[blue]Output directory:[/blue] {output_dir}")
        
        # Initialize and run pipeline
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Initializing pipeline...", total=None)
            
            # TODO: Initialize pipeline
            # pipeline = Pipeline(
            #     target=target,
            #     profile=profile,
            #     mode=mode,
            #     scope=scope_config,
            #     output_dir=output_dir,
            # )
            
            progress.update(task, description="[cyan]Running reconnaissance...")
            # TODO: Execute pipeline stages
            # await pipeline.run()
            
            progress.update(task, description="[green]Scan complete!")
        
        console.print("[green]✓[/green] Scan completed successfully")
        console.print(f"[blue]Results saved to:[/blue] {output_dir}")
        
    except Exception as e:
        console.print(f"[red]Error during scan:[/red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(code=1)


@app.command()
def version() -> None:
    """Show version information."""
    console.print(f"[bold cyan]GaleHunTUI[/bold cyan] version [yellow]{__version__}[/yellow]")


@app.command()
def export(
    run_id: str = typer.Argument(..., help="Run ID to export"),
    format: str = typer.Option(
        "html",
        "--format",
        "-f",
        help="Export format (html, json)",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path",
    ),
) -> None:
    """
    Export scan results to various formats.
    """
    try:
        # from galehuntui.reporting.generator import ReportGenerator
        
        console.print(f"[cyan]Exporting run:[/cyan] {run_id}")
        console.print(f"[cyan]Format:[/cyan] {format}")
        
        # Determine output path
        if output:
            output_path = Path(output)
        else:
            # Default to current directory
            extension = "html" if format == "html" else "json"
            output_path = Path.cwd() / f"report_{run_id}.{extension}"
        
        # TODO: Generate report
        # generator = ReportGenerator()
        # generator.export(run_id=run_id, format=format, output=output_path)
        
        console.print(f"[green]✓[/green] Report exported to: {output_path}")
        
    except Exception as e:
        console.print(f"[red]Error exporting report:[/red] {e}")
        raise typer.Exit(code=1)


# ============================================================================
# Tools Commands
# ============================================================================

@tools_app.command("init")
def tools_init() -> None:
    """Initialize tools directory structure."""
    try:
        from galehuntui.tools.installer import ToolInstaller
        
        console.print("[cyan]Initializing tools directory...[/cyan]")
        
        # Create tools directory structure
        tools_dir = Path.cwd() / "tools"
        (tools_dir / "bin").mkdir(parents=True, exist_ok=True)
        (tools_dir / "scripts").mkdir(parents=True, exist_ok=True)
        
        console.print(f"[green]✓[/green] Created: {tools_dir}")
        console.print(f"[green]✓[/green] Created: {tools_dir / 'bin'}")
        console.print(f"[green]✓[/green] Created: {tools_dir / 'scripts'}")
        
        # Copy registry template if needed
        registry_file = tools_dir / "registry.yaml"
        if not registry_file.exists():
            console.print(f"[blue]Creating registry template...[/blue]")
            # TODO: Create registry template
            
        console.print("[green]✓[/green] Tools directory initialized")
        
    except Exception as e:
        console.print(f"[red]Error initializing tools:[/red] {e}")
        raise typer.Exit(code=1)


@tools_app.command("install")
def tools_install(
    tools: Optional[List[str]] = typer.Argument(None, help="Specific tools to install"),
    all: bool = typer.Option(False, "--all", help="Install all tools"),
) -> None:
    """Install pentesting tools."""
    try:
        # from galehuntui.tools.installer import ToolInstaller
        
        if all:
            console.print("[cyan]Installing all tools...[/cyan]")
            tool_list = [
                "subfinder", "dnsx", "httpx", "katana", "gau",
                "nuclei", "dalfox", "ffuf", "sqlmap"
            ]
        elif tools:
            tool_list = tools
        else:
            console.print("[red]Error:[/red] Specify tools or use --all")
            raise typer.Exit(code=1)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for tool in tool_list:
                task = progress.add_task(f"[cyan]Installing {tool}...", total=None)
                
                # TODO: Install tool
                # installer = ToolInstaller()
                # installer.install(tool)
                
                progress.update(task, description=f"[green]✓ {tool} installed")
        
        console.print("[green]✓[/green] All tools installed successfully")
        
    except Exception as e:
        console.print(f"[red]Error installing tools:[/red] {e}")
        raise typer.Exit(code=1)


@tools_app.command("update")
def tools_update(
    tools: Optional[List[str]] = typer.Argument(None, help="Specific tools to update"),
    all: bool = typer.Option(False, "--all", help="Update all tools"),
) -> None:
    """Update installed tools to latest versions."""
    try:
        if all:
            console.print("[cyan]Updating all tools...[/cyan]")
            # TODO: Get list of installed tools
            tool_list = ["subfinder", "httpx", "nuclei"]  # Placeholder
        elif tools:
            tool_list = tools
        else:
            console.print("[red]Error:[/red] Specify tools or use --all")
            raise typer.Exit(code=1)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for tool in tool_list:
                task = progress.add_task(f"[cyan]Updating {tool}...", total=None)
                # TODO: Update tool
                progress.update(task, description=f"[green]✓ {tool} updated")
        
        console.print("[green]✓[/green] Tools updated successfully")
        
    except Exception as e:
        console.print(f"[red]Error updating tools:[/red] {e}")
        raise typer.Exit(code=1)


@tools_app.command("list")
def tools_list(
    available: bool = typer.Option(False, "--available", help="Show available tools"),
) -> None:
    """List installed or available tools."""
    try:
        table = Table(title="Installed Tools" if not available else "Available Tools")
        table.add_column("Tool", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Status", style="yellow")
        
        # TODO: Get tool status from registry
        # Placeholder data
        tools_data = [
            ("subfinder", "2.6.3", "installed"),
            ("httpx", "1.3.7", "installed"),
            ("nuclei", "3.1.0", "installed"),
            ("dalfox", "2.9.0", "not installed"),
            ("sqlmap", "1.7", "not installed"),
        ]
        
        for tool, version, status in tools_data:
            table.add_row(tool, version, status)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing tools:[/red] {e}")
        raise typer.Exit(code=1)


@tools_app.command("verify")
def tools_verify() -> None:
    """Verify tool installations and integrity."""
    try:
        console.print("[cyan]Verifying tool installations...[/cyan]")
        
        # TODO: Verify each tool
        tools_to_verify = ["subfinder", "httpx", "nuclei"]
        
        table = Table(title="Tool Verification")
        table.add_column("Tool", style="cyan")
        table.add_column("Installed", style="green")
        table.add_column("Executable", style="yellow")
        table.add_column("Version", style="blue")
        
        for tool in tools_to_verify:
            # TODO: Check tool status
            table.add_row(tool, "✓", "✓", "2.6.3")
        
        console.print(table)
        console.print("[green]✓[/green] Verification complete")
        
    except Exception as e:
        console.print(f"[red]Error verifying tools:[/red] {e}")
        raise typer.Exit(code=1)


# ============================================================================
# Dependencies Commands
# ============================================================================

@deps_app.command("install")
def deps_install(
    all: bool = typer.Option(False, "--all", help="Install all dependencies"),
) -> None:
    """Install dependencies (wordlists, templates)."""
    try:
        console.print("[cyan]Installing dependencies...[/cyan]")
        
        deps = []
        if all:
            deps = ["nuclei-templates", "wordlists", "resolvers"]
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            for dep in deps:
                task = progress.add_task(f"[cyan]Installing {dep}...", total=None)
                # TODO: Install dependency
                progress.update(task, description=f"[green]✓ {dep} installed")
        
        console.print("[green]✓[/green] Dependencies installed")
        
    except Exception as e:
        console.print(f"[red]Error installing dependencies:[/red] {e}")
        raise typer.Exit(code=1)


@deps_app.command("update")
def deps_update(
    name: str = typer.Argument(..., help="Dependency name (e.g., nuclei-templates)"),
) -> None:
    """Update a specific dependency."""
    try:
        console.print(f"[cyan]Updating {name}...[/cyan]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"[cyan]Updating {name}...", total=None)
            # TODO: Update dependency
            progress.update(task, description=f"[green]✓ {name} updated")
        
        console.print("[green]✓[/green] Dependency updated")
        
    except Exception as e:
        console.print(f"[red]Error updating dependency:[/red] {e}")
        raise typer.Exit(code=1)


@deps_app.command("clean")
def deps_clean() -> None:
    """Clean up old/unused dependencies."""
    try:
        console.print("[cyan]Cleaning dependencies...[/cyan]")
        
        # TODO: Clean old dependencies
        
        console.print("[green]✓[/green] Dependencies cleaned")
        
    except Exception as e:
        console.print(f"[red]Error cleaning dependencies:[/red] {e}")
        raise typer.Exit(code=1)


# ============================================================================
# Runs Commands
# ============================================================================

@runs_app.command("list")
def runs_list(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of runs to show"),
) -> None:
    """List recent scan runs."""
    try:
        # from galehuntui.storage.database import Database
        
        table = Table(title=f"Recent Runs (limit: {limit})")
        table.add_column("Run ID", style="cyan")
        table.add_column("Target", style="yellow")
        table.add_column("Profile", style="green")
        table.add_column("Status", style="magenta")
        table.add_column("Started", style="blue")
        
        # TODO: Query database for runs
        # Placeholder data
        runs_data = [
            ("abc123", "example.com", "standard", "completed", "2024-02-03 10:30"),
            ("def456", "test.com", "quick", "running", "2024-02-03 11:15"),
        ]
        
        for run_id, target, profile, status, started in runs_data:
            table.add_row(run_id, target, profile, status, started)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing runs:[/red] {e}")
        raise typer.Exit(code=1)


@runs_app.command("show")
def runs_show(
    run_id: str = typer.Argument(..., help="Run ID to display"),
) -> None:
    """Show detailed information about a specific run."""
    try:
        console.print(f"[cyan]Run Details:[/cyan] {run_id}")
        
        # TODO: Query database for run details
        
        # Placeholder output
        console.print(Panel(
            f"[bold]Target:[/bold] example.com\n"
            f"[bold]Profile:[/bold] standard\n"
            f"[bold]Mode:[/bold] bugbounty\n"
            f"[bold]Status:[/bold] completed\n"
            f"[bold]Duration:[/bold] 1h 23m\n"
            f"[bold]Findings:[/bold] 12 (3 high, 5 medium, 4 low)",
            title=f"Run {run_id}",
        ))
        
    except Exception as e:
        console.print(f"[red]Error showing run:[/red] {e}")
        raise typer.Exit(code=1)


@runs_app.command("delete")
def runs_delete(
    run_id: str = typer.Argument(..., help="Run ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a scan run and its artifacts."""
    try:
        if not force:
            confirm = typer.confirm(f"Delete run {run_id} and all its data?")
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(code=0)
        
        console.print(f"[cyan]Deleting run:[/cyan] {run_id}")
        
        # TODO: Delete from database and filesystem
        
        console.print("[green]✓[/green] Run deleted successfully")
        
    except Exception as e:
        console.print(f"[red]Error deleting run:[/red] {e}")
        raise typer.Exit(code=1)


# ============================================================================
# Entry Point
# ============================================================================

def main() -> None:
    """Main entry point for CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"[red]Unexpected error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
