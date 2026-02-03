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
plugins_app = typer.Typer(help="Manage plugins")

# Register sub-apps
app.add_typer(tools_app, name="tools")
app.add_typer(deps_app, name="deps")
app.add_typer(runs_app, name="runs")
app.add_typer(plugins_app, name="plugins")

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
        
        # Launch TUI with config path
        app_instance = GaleHunTUIApp(config_path=config)
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
    resume: Optional[str] = typer.Option(
        None,
        "--resume",
        "-r",
        help="Resume a previous run by ID",
    ),
) -> None:
    """
    Execute a scan run from the command line.
    
    This runs the orchestrator in headless mode without the TUI.
    """
    import asyncio
    from galehuntui.core.config import load_scope_config, load_profile_config
    from galehuntui.core.models import ScopeConfig, ScanProfile
    from galehuntui.orchestrator.pipeline import PipelineOrchestrator
    from galehuntui.storage.database import Database
    from galehuntui.tools.installer import ToolInstaller
    
    try:
        console.print(Panel.fit(
            f"[bold cyan]GaleHunTUI Scan[/bold cyan]\n\n"
            f"Target: [yellow]{target}[/yellow]\n"
            f"Profile: [green]{profile}[/green]\n"
            f"Mode: [magenta]{mode.value}[/magenta]"
            + (f"\nResume: [blue]{resume}[/blue]" if resume else ""),
            title="Scan Configuration",
        ))
        
        if not target or "." not in target:
            console.print("[red]Error:[/red] Invalid target domain")
            raise typer.Exit(code=1)
        
        if scope:
            console.print(f"[blue]Loading scope from:[/blue] {scope}")
            scope_config = load_scope_config(scope)
        else:
            scope_config = ScopeConfig(
                target_domain=target,
                allowlist=[f"*.{target}", target],
                denylist=[],
            )
        
        console.print(f"[blue]Loading profile:[/blue] {profile}")
        loaded_profile = load_profile_config(profile)
        if not isinstance(loaded_profile, ScanProfile):
            console.print(f"[red]Error:[/red] Profile '{profile}' not found")
            raise typer.Exit(code=1)
        scan_profile: ScanProfile = loaded_profile
        
        data_dir = Path.home() / ".local" / "share" / "galehuntui"
        runs_dir = data_dir / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        
        if output:
            output_dir = Path(output)
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = runs_dir
        
        console.print(f"[blue]Output directory:[/blue] {output_dir}")
        
        db_path = data_dir / "galehuntui.db"
        db = Database(db_path)
        db.init_db()
        
        tools_dir = Path.cwd() / "tools"
        installer = ToolInstaller(tools_dir)
        
        adapters = {}
        adapter_modules = {
            "subfinder": "galehuntui.tools.adapters.subfinder",
            "dnsx": "galehuntui.tools.adapters.dnsx",
            "httpx": "galehuntui.tools.adapters.httpx",
            "katana": "galehuntui.tools.adapters.katana",
            "gau": "galehuntui.tools.adapters.gau",
            "nuclei": "galehuntui.tools.adapters.nuclei",
            "dalfox": "galehuntui.tools.adapters.dalfox",
            "ffuf": "galehuntui.tools.adapters.ffuf",
            "sqlmap": "galehuntui.tools.adapters.sqlmap",
        }
        
        for tool_name in scan_profile.steps:
            if tool_name in adapter_modules:
                try:
                    import importlib
                    mod = importlib.import_module(adapter_modules[tool_name])
                    adapter_class = getattr(mod, f"{tool_name.capitalize()}Adapter", None)
                    if adapter_class:
                        bin_path = installer.bin_dir / tool_name
                        adapters[tool_name] = adapter_class(bin_path)
                except (ImportError, AttributeError) as e:
                    if verbose:
                        console.print(f"[yellow]Warning:[/yellow] Could not load adapter for {tool_name}: {e}")
        
        pipeline = PipelineOrchestrator.create_standard_pipeline(
            adapters=adapters,
            target=target,
            profile=scan_profile,
            scope=scope_config,
            engagement_mode=mode,
        )
        pipeline.db = db
        
        async def run_pipeline():
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]Initializing pipeline...", total=None)
                
                if resume:
                    progress.update(task, description=f"[cyan]Resuming run {resume}...")
                    state = await pipeline.run_with_resume(target, resume_id=resume)
                else:
                    progress.update(task, description="[cyan]Running scan pipeline...")
                    state = await pipeline.run(target)
                
                progress.update(task, description="[green]Scan complete!")
                return state
        
        state = asyncio.run(run_pipeline())
        
        console.print("[green]✓[/green] Scan completed successfully")
        console.print(f"[blue]Run ID:[/blue] {state.metadata.id}")
        console.print(f"[blue]Findings:[/blue] {state.metadata.total_findings}")
        console.print(f"[blue]Results saved to:[/blue] {state.metadata.run_dir}")
        
        if state.metadata.total_findings > 0:
            console.print("\n[bold]Findings by Severity:[/bold]")
            for severity, count in state.metadata.findings_by_severity.items():
                if count > 0:
                    color = {"critical": "red", "high": "red", "medium": "yellow", "low": "blue", "info": "dim"}.get(severity, "white")
                    console.print(f"  [{color}]{severity.capitalize()}:[/{color}] {count}")
        
        db.close()
        
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
    from galehuntui.storage.database import Database
    from galehuntui.reporting.generator import ReportGenerator
    
    try:
        data_dir = Path.home() / ".local" / "share" / "galehuntui"
        db_path = data_dir / "galehuntui.db"
        
        if not db_path.exists():
            console.print("[red]Error:[/red] Database not found. No runs available.")
            raise typer.Exit(code=1)
        
        db = Database(db_path)
        db.init_db()
        
        runs = db.list_runs(limit=100)
        matching_runs = [r for r in runs if r.id.startswith(run_id)]
        
        if not matching_runs:
            console.print(f"[red]Error:[/red] Run '{run_id}' not found")
            db.close()
            raise typer.Exit(code=1)
        
        if len(matching_runs) > 1:
            console.print(f"[yellow]Multiple runs match '{run_id}':[/yellow]")
            for r in matching_runs:
                console.print(f"  - {r.id}")
            console.print("Please provide a more specific ID.")
            db.close()
            raise typer.Exit(code=1)
        
        run = matching_runs[0]
        
        console.print(f"[cyan]Exporting run:[/cyan] {run.id}")
        console.print(f"[cyan]Format:[/cyan] {format}")
        
        if output:
            output_path = Path(output)
        else:
            extension = "html" if format == "html" else "json"
            run_id_short = run.id[:12]
            output_path = Path.cwd() / f"report_{run_id_short}.{extension}"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        generator = ReportGenerator(db)
        report = generator.generate_report(run.id)
        
        if format == "html":
            generator.export_html(report, output_path)
        elif format == "json":
            generator.export_json(report, output_path)
        else:
            console.print(f"[red]Error:[/red] Unsupported format '{format}'. Use 'html' or 'json'.")
            db.close()
            raise typer.Exit(code=1)
        
        db.close()
        
        console.print(f"[green]✓[/green] Report exported to: {output_path}")
        console.print(f"[dim]Report includes {report.statistics.total_findings} findings[/dim]")
        
    except typer.Exit:
        raise
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
            # Create registry template from the bundled one
            bundled_registry = Path(__file__).parent / "tools" / "registry.yaml"
            if bundled_registry.exists():
                import shutil
                shutil.copy(bundled_registry, registry_file)
                console.print(f"[green]✓[/green] Created: {registry_file}")
            else:
                # Create minimal registry template
                registry_content = """# Tool Registry for GaleHunTUI
# Defines all supported security tools and their installation methods

tools:
  subfinder:
    install_method: "github_release"
    repo: "projectdiscovery/subfinder"
    binary_name: "subfinder"
    required: true
    description: "Fast passive subdomain enumeration tool"
    asset_patterns: []

  dnsx:
    install_method: "github_release"
    repo: "projectdiscovery/dnsx"
    binary_name: "dnsx"
    required: true
    description: "Fast and multi-purpose DNS toolkit"
    asset_patterns: []

  httpx:
    install_method: "github_release"
    repo: "projectdiscovery/httpx"
    binary_name: "httpx"
    required: true
    description: "Fast HTTP probing tool"
    asset_patterns: []

  katana:
    install_method: "github_release"
    repo: "projectdiscovery/katana"
    binary_name: "katana"
    required: true
    description: "Next-generation crawling and spidering framework"
    asset_patterns: []

  gau:
    install_method: "github_release"
    repo: "lc/gau"
    binary_name: "gau"
    required: true
    description: "Fetch known URLs from AlienVault, Wayback Machine, and Common Crawl"
    asset_patterns: []

  nuclei:
    install_method: "github_release"
    repo: "projectdiscovery/nuclei"
    binary_name: "nuclei"
    required: true
    description: "Fast and customizable vulnerability scanner"
    asset_patterns: []

  dalfox:
    install_method: "github_release"
    repo: "hahwul/dalfox"
    binary_name: "dalfox"
    required: false
    description: "Parameter analysis and XSS scanning tool"
    asset_patterns: []

  ffuf:
    install_method: "github_release"
    repo: "ffuf/ffuf"
    binary_name: "ffuf"
    required: false
    description: "Fast web fuzzer"
    asset_patterns: []

  sqlmap:
    install_method: "git"
    repo_url: "https://github.com/sqlmapproject/sqlmap.git"
    branch: "master"
    required: false
    description: "Automatic SQL injection and database takeover tool"

  hydra:
    install_method: "system"
    package_name: "hydra"
    required: false
    description: "Network logon cracker"

  wfuzz:
    install_method: "pip"
    package_name: "wfuzz"
    required: false
    description: "Web application fuzzer"
"""
                registry_file.write_text(registry_content)
                console.print(f"[green]✓[/green] Created: {registry_file}")
            
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
    import asyncio
    from galehuntui.tools.installer import ToolInstaller
    
    try:
        tools_dir = Path.cwd() / "tools"
        installer = ToolInstaller(tools_dir)
        
        if all:
            console.print("[cyan]Installing all tools...[/cyan]")
            registry = installer.load_registry()
            tool_list = list(registry.get("tools", {}).keys())
        elif tools:
            tool_list = tools
        else:
            console.print("[red]Error:[/red] Specify tools or use --all")
            raise typer.Exit(code=1)
        
        async def install_tools():
            results = {}
            for tool in tool_list:
                console.print(f"[cyan]Installing {tool}...[/cyan]")
                try:
                    path = await installer.install_tool(tool)
                    console.print(f"[green]✓[/green] {tool} installed at {path}")
                    results[tool] = path
                except Exception as e:
                    console.print(f"[red]✗[/red] {tool} failed: {e}")
                    results[tool] = e
            return results
        
        asyncio.run(install_tools())
        console.print("[green]✓[/green] Installation complete")
        
    except Exception as e:
        console.print(f"[red]Error installing tools:[/red] {e}")
        raise typer.Exit(code=1)


@tools_app.command("update")
def tools_update(
    tools: Optional[List[str]] = typer.Argument(None, help="Specific tools to update"),
    all: bool = typer.Option(False, "--all", help="Update all tools"),
) -> None:
    """Update installed tools to latest versions."""
    import asyncio
    from galehuntui.tools.installer import ToolInstaller
    
    try:
        tools_dir = Path.cwd() / "tools"
        installer = ToolInstaller(tools_dir)
        
        if all:
            console.print("[cyan]Updating all installed tools...[/cyan]")
            # Get list of installed tools
            registry = installer.load_registry()
            tool_list = [
                name for name in registry.get("tools", {}).keys()
                if installer.verify_tool(name)
            ]
            if not tool_list:
                console.print("[yellow]No tools installed yet. Use 'galehuntui tools install --all' first.[/yellow]")
                raise typer.Exit(code=0)
        elif tools:
            tool_list = tools
        else:
            console.print("[red]Error:[/red] Specify tools or use --all")
            raise typer.Exit(code=1)
        
        async def update_tools():
            for tool in tool_list:
                console.print(f"[cyan]Updating {tool}...[/cyan]")
                try:
                    path = await installer.install_tool(tool)
                    console.print(f"[green]✓[/green] {tool} updated at {path}")
                except Exception as e:
                    console.print(f"[red]✗[/red] {tool} failed: {e}")
        
        asyncio.run(update_tools())
        console.print("[green]✓[/green] Tools updated successfully")
        
    except Exception as e:
        console.print(f"[red]Error updating tools:[/red] {e}")
        raise typer.Exit(code=1)


@tools_app.command("list")
def tools_list(
    available: bool = typer.Option(False, "--available", help="Show available tools"),
) -> None:
    """List installed or available tools."""
    import asyncio
    from galehuntui.tools.installer import ToolInstaller
    
    try:
        tools_dir = Path.cwd() / "tools"
        installer = ToolInstaller(tools_dir)
        registry = installer.load_registry()
        
        table = Table(title="Installed Tools" if not available else "Available Tools")
        table.add_column("Tool", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("Required", style="blue")
        
        async def get_versions():
            tools_data = []
            for tool_name, config in registry.get("tools", {}).items():
                is_installed = installer.verify_tool(tool_name)
                version = "-"
                if is_installed:
                    version = await installer.get_tool_version(tool_name) or "installed"
                status = "[green]installed[/green]" if is_installed else "[red]not installed[/red]"
                required = "Yes" if config.get("required", False) else "No"
                tools_data.append((tool_name, version, status, required))
            return tools_data
        
        tools_data = asyncio.run(get_versions())
        
        for tool, version, status, required in tools_data:
            table.add_row(tool, version, status, required)
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing tools:[/red] {e}")
        raise typer.Exit(code=1)


@tools_app.command("verify")
def tools_verify() -> None:
    """Verify tool installations and integrity."""
    import asyncio
    from galehuntui.tools.installer import ToolInstaller
    
    try:
        tools_dir = Path.cwd() / "tools"
        installer = ToolInstaller(tools_dir)
        registry = installer.load_registry()
        
        console.print("[cyan]Verifying tool installations...[/cyan]")
        
        table = Table(title="Tool Verification")
        table.add_column("Tool", style="cyan")
        table.add_column("Installed", style="green")
        table.add_column("Executable", style="yellow")
        table.add_column("Version", style="blue")
        
        async def verify_all():
            all_ok = True
            for tool_name in registry.get("tools", {}).keys():
                is_installed = installer.verify_tool(tool_name)
                
                binary_path = installer.bin_dir / tool_name
                is_executable = binary_path.exists() and binary_path.is_file()
                
                version = "-"
                if is_installed:
                    version = await installer.get_tool_version(tool_name) or "unknown"
                
                installed_mark = "[green]✓[/green]" if is_installed else "[red]✗[/red]"
                exec_mark = "[green]✓[/green]" if is_executable else "[yellow]–[/yellow]"
                
                if not is_installed:
                    all_ok = False
                
                table.add_row(tool_name, installed_mark, exec_mark, version)
            return all_ok
        
        all_ok = asyncio.run(verify_all())
        
        console.print(table)
        
        if all_ok:
            console.print("[green]✓[/green] Verification complete - all tools available")
        else:
            console.print("[yellow]![/yellow] Some tools are not installed. Run 'galehuntui tools install --all'")
        
    except Exception as e:
        console.print(f"[red]Error verifying tools:[/red] {e}")
        raise typer.Exit(code=1)


# ============================================================================
# Dependencies Commands
# ============================================================================

@deps_app.command("install")
def deps_install(
    names: Optional[List[str]] = typer.Argument(None, help="Specific dependencies to install"),
    all: bool = typer.Option(False, "--all", help="Install all dependencies"),
) -> None:
    """Install dependencies (wordlists, templates)."""
    import asyncio
    from galehuntui.tools.deps.manager import DependencyManager
    
    try:
        deps_dir = Path.home() / ".local" / "share" / "galehuntui" / "deps"
        manager = DependencyManager(deps_dir)
        
        async def install_deps():
            if all:
                console.print("[cyan]Installing all dependencies...[/cyan]")
                results = await manager.install_all(skip_errors=True)
                for dep_id, result in results.items():
                    if isinstance(result, Exception):
                        console.print(f"[red]✗[/red] {dep_id}: {result}")
                    else:
                        console.print(f"[green]✓[/green] {dep_id} installed")
                return results
            elif names:
                for name in names:
                    console.print(f"[cyan]Installing {name}...[/cyan]")
                    try:
                        await manager.install(name)
                        console.print(f"[green]✓[/green] {name} installed")
                    except Exception as e:
                        console.print(f"[red]✗[/red] {name}: {e}")
            else:
                console.print("[red]Error:[/red] Specify dependencies or use --all")
                raise typer.Exit(code=1)
        
        asyncio.run(install_deps())
        console.print("[green]✓[/green] Dependencies installed")
        
    except Exception as e:
        console.print(f"[red]Error installing dependencies:[/red] {e}")
        raise typer.Exit(code=1)


@deps_app.command("update")
def deps_update(
    name: str = typer.Argument(..., help="Dependency name (e.g., nuclei-templates)"),
) -> None:
    """Update a specific dependency."""
    import asyncio
    from galehuntui.tools.deps.manager import DependencyManager
    
    try:
        deps_dir = Path.home() / ".local" / "share" / "galehuntui" / "deps"
        manager = DependencyManager(deps_dir)
        
        async def update_dep():
            console.print(f"[cyan]Updating {name}...[/cyan]")
            result = await manager.update(name)
            if result:
                console.print(f"[green]✓[/green] {name} updated")
            else:
                console.print(f"[yellow]![/yellow] {name} - no updates available")
        
        asyncio.run(update_dep())
        
    except Exception as e:
        console.print(f"[red]Error updating dependency:[/red] {e}")
        raise typer.Exit(code=1)


@deps_app.command("list")
def deps_list() -> None:
    """List available dependencies and their status."""
    import asyncio
    from galehuntui.tools.deps.manager import DependencyManager
    
    try:
        deps_dir = Path.home() / ".local" / "share" / "galehuntui" / "deps"
        manager = DependencyManager(deps_dir)
        
        async def get_deps():
            return await manager.get_dependencies()
        
        deps = asyncio.run(get_deps())
        
        if not deps:
            console.print("[yellow]No dependencies defined in registry.[/yellow]")
            return
        
        table = Table(title="Dependencies")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Type", style="blue")
        table.add_column("Status", style="yellow")
        table.add_column("Size", style="dim")
        
        for dep in deps:
            status_style = "[green]installed[/green]" if dep.status.value == "installed" else "[red]not installed[/red]"
            table.add_row(
                dep.id,
                dep.name,
                dep.type.value,
                status_style,
                dep.size_estimate or "-",
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing dependencies:[/red] {e}")
        raise typer.Exit(code=1)


@deps_app.command("clean")
def deps_clean() -> None:
    """Clean up old/unused dependencies."""
    import asyncio
    import shutil
    from galehuntui.tools.deps.manager import DependencyManager
    
    try:
        deps_dir = Path.home() / ".local" / "share" / "galehuntui" / "deps"
        manager = DependencyManager(deps_dir)
        
        console.print("[cyan]Cleaning dependencies...[/cyan]")
        
        async def clean_deps():
            deps = await manager.get_dependencies()
            cleaned = 0
            for dep in deps:
                if dep.installed_path and dep.installed_path.exists():
                    git_dir = dep.installed_path / ".git"
                    if git_dir.exists():
                        objects_dir = git_dir / "objects"
                        pack_dir = objects_dir / "pack" if objects_dir.exists() else None
                        if pack_dir and pack_dir.exists():
                            for loose in objects_dir.iterdir():
                                if loose.is_dir() and loose.name != "pack" and loose.name != "info":
                                    shutil.rmtree(loose)
                                    cleaned += 1
            return cleaned
        
        cleaned = asyncio.run(clean_deps())
        console.print(f"[green]✓[/green] Dependencies cleaned ({cleaned} loose object directories removed)")
        
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
    from galehuntui.storage.database import Database
    
    try:
        data_dir = Path.home() / ".local" / "share" / "galehuntui"
        db_path = data_dir / "galehuntui.db"
        
        if not db_path.exists():
            console.print("[yellow]No runs found. Database not initialized yet.[/yellow]")
            console.print("[dim]Run a scan first with: galehuntui run <target>[/dim]")
            return
        
        db = Database(db_path)
        db.init_db()
        
        runs = db.list_runs(limit=limit)
        
        if not runs:
            console.print("[yellow]No scan runs found.[/yellow]")
            db.close()
            return
        
        table = Table(title=f"Recent Runs (showing {len(runs)} of {limit} max)")
        table.add_column("Run ID", style="cyan")
        table.add_column("Target", style="yellow")
        table.add_column("Profile", style="green")
        table.add_column("Status", style="magenta")
        table.add_column("Started", style="blue")
        table.add_column("Findings", style="white")
        
        for run in runs:
            status_color = {
                "completed": "green",
                "running": "yellow",
                "failed": "red",
                "cancelled": "dim",
                "pending": "blue",
                "paused": "yellow",
            }.get(run.state.value, "white")
            
            started = run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else "-"
            run_id_short = run.id[:12] if len(run.id) > 12 else run.id
            
            table.add_row(
                run_id_short,
                run.target,
                run.profile,
                f"[{status_color}]{run.state.value}[/{status_color}]",
                started,
                str(run.total_findings),
            )
        
        console.print(table)
        db.close()
        
    except Exception as e:
        console.print(f"[red]Error listing runs:[/red] {e}")
        raise typer.Exit(code=1)


@runs_app.command("show")
def runs_show(
    run_id: str = typer.Argument(..., help="Run ID to display"),
) -> None:
    """Show detailed information about a specific run."""
    from galehuntui.storage.database import Database
    
    try:
        data_dir = Path.home() / ".local" / "share" / "galehuntui"
        db_path = data_dir / "galehuntui.db"
        
        if not db_path.exists():
            console.print("[red]Error:[/red] Database not found. No runs available.")
            raise typer.Exit(code=1)
        
        db = Database(db_path)
        db.init_db()
        
        runs = db.list_runs(limit=100)
        matching_runs = [r for r in runs if r.id.startswith(run_id)]
        
        if not matching_runs:
            console.print(f"[red]Error:[/red] Run '{run_id}' not found")
            db.close()
            raise typer.Exit(code=1)
        
        if len(matching_runs) > 1:
            console.print(f"[yellow]Multiple runs match '{run_id}':[/yellow]")
            for r in matching_runs:
                console.print(f"  - {r.id}")
            console.print("Please provide a more specific ID.")
            db.close()
            raise typer.Exit(code=1)
        
        run = matching_runs[0]
        findings = db.get_findings_for_run(run.id)
        steps = db.get_steps(run.id)
        
        duration_str = "N/A"
        if run.duration:
            hours = int(run.duration // 3600)
            minutes = int((run.duration % 3600) // 60)
            seconds = int(run.duration % 60)
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
        
        severity_breakdown = []
        for sev in ["critical", "high", "medium", "low", "info"]:
            count = run.findings_by_severity.get(sev, 0)
            if count > 0:
                severity_breakdown.append(f"{count} {sev}")
        severity_str = ", ".join(severity_breakdown) if severity_breakdown else "None"
        
        status_color = {
            "completed": "green",
            "running": "yellow",
            "failed": "red",
            "cancelled": "dim",
            "pending": "blue",
            "paused": "yellow",
        }.get(run.state.value, "white")
        
        console.print(Panel(
            f"[bold]Target:[/bold] {run.target}\n"
            f"[bold]Profile:[/bold] {run.profile}\n"
            f"[bold]Mode:[/bold] {run.engagement_mode.value}\n"
            f"[bold]Status:[/bold] [{status_color}]{run.state.value}[/{status_color}]\n"
            f"[bold]Created:[/bold] {run.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"[bold]Duration:[/bold] {duration_str}\n"
            f"[bold]Findings:[/bold] {run.total_findings} ({severity_str})\n"
            f"[bold]Run Directory:[/bold] {run.run_dir}",
            title=f"Run {run.id}",
        ))
        
        if steps:
            console.print("\n[bold]Pipeline Steps:[/bold]")
            steps_table = Table(show_header=True)
            steps_table.add_column("Step", style="cyan")
            steps_table.add_column("Status", style="yellow")
            steps_table.add_column("Duration", style="blue")
            steps_table.add_column("Findings", style="green")
            
            for step in steps:
                step_status_color = {
                    "completed": "green",
                    "running": "yellow",
                    "failed": "red",
                    "skipped": "dim",
                    "pending": "blue",
                }.get(step.status.value, "white")
                
                step_duration = f"{step.duration:.1f}s" if step.duration else "-"
                
                steps_table.add_row(
                    step.name,
                    f"[{step_status_color}]{step.status.value}[/{step_status_color}]",
                    step_duration,
                    str(step.findings_count),
                )
            
            console.print(steps_table)
        
        if findings:
            console.print(f"\n[bold]Top Findings ({len(findings)} total):[/bold]")
            findings_table = Table(show_header=True)
            findings_table.add_column("Severity", style="yellow")
            findings_table.add_column("Type", style="cyan")
            findings_table.add_column("URL", style="white", max_width=50)
            findings_table.add_column("Tool", style="blue")
            
            for finding in findings[:10]:
                sev_color = {
                    "critical": "red bold",
                    "high": "red",
                    "medium": "yellow",
                    "low": "blue",
                    "info": "dim",
                }.get(finding.severity.value, "white")
                
                url_display = finding.url[:47] + "..." if len(finding.url) > 50 else finding.url
                
                findings_table.add_row(
                    f"[{sev_color}]{finding.severity.value}[/{sev_color}]",
                    finding.type,
                    url_display,
                    finding.tool,
                )
            
            console.print(findings_table)
            
            if len(findings) > 10:
                console.print(f"[dim]... and {len(findings) - 10} more findings[/dim]")
        
        db.close()
        
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error showing run:[/red] {e}")
        raise typer.Exit(code=1)


@runs_app.command("delete")
def runs_delete(
    run_id: str = typer.Argument(..., help="Run ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a scan run and its artifacts."""
    from galehuntui.storage.database import Database
    from galehuntui.storage.artifacts import ArtifactStorage
    
    try:
        data_dir = Path.home() / ".local" / "share" / "galehuntui"
        db_path = data_dir / "galehuntui.db"
        runs_dir = data_dir / "runs"
        
        if not db_path.exists():
            console.print("[red]Error:[/red] Database not found. No runs available.")
            raise typer.Exit(code=1)
        
        db = Database(db_path)
        db.init_db()
        
        runs = db.list_runs(limit=100)
        matching_runs = [r for r in runs if r.id.startswith(run_id)]
        
        if not matching_runs:
            console.print(f"[red]Error:[/red] Run '{run_id}' not found")
            db.close()
            raise typer.Exit(code=1)
        
        if len(matching_runs) > 1:
            console.print(f"[yellow]Multiple runs match '{run_id}':[/yellow]")
            for r in matching_runs:
                console.print(f"  - {r.id}")
            console.print("Please provide a more specific ID.")
            db.close()
            raise typer.Exit(code=1)
        
        run = matching_runs[0]
        
        if not force:
            confirm = typer.confirm(
                f"Delete run {run.id[:12]}... ({run.target}, {run.total_findings} findings) and all its data?"
            )
            if not confirm:
                console.print("[yellow]Cancelled[/yellow]")
                db.close()
                raise typer.Exit(code=0)
        
        console.print(f"[cyan]Deleting run:[/cyan] {run.id}")
        
        artifact_storage = ArtifactStorage(runs_dir)
        artifacts_deleted = artifact_storage.delete_run_artifacts(run.id)
        
        db.delete_steps(run.id)
        db_deleted = db.delete_run(run.id)
        
        db.close()
        
        if db_deleted:
            console.print("[green]✓[/green] Database records deleted")
        if artifacts_deleted:
            console.print("[green]✓[/green] Artifacts deleted")
        
        console.print("[green]✓[/green] Run deleted successfully")
        
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error deleting run:[/red] {e}")
        raise typer.Exit(code=1)


# ============================================================================
# Plugins Commands
# ============================================================================

@plugins_app.command("list")
def plugins_list() -> None:
    """List discovered plugins."""
    try:
        from galehuntui.plugins import PluginManager
        
        manager = PluginManager()
        manager.discover()
        
        plugins = manager.list_plugins()
        
        if not plugins:
            console.print("[yellow]No plugins discovered.[/yellow]")
            console.print(f"[dim]Plugin directory: ~/.local/share/galehuntui/plugins/[/dim]")
            return
        
        table = Table(title="Discovered Plugins")
        table.add_column("Name", style="cyan")
        table.add_column("Version", style="green")
        table.add_column("Description", style="white")
        table.add_column("State", style="yellow")
        
        for metadata in plugins:
            info = manager.get_plugin_info(metadata.name)
            state = info.plugin.state.value if info else "unknown"
            table.add_row(
                metadata.name,
                metadata.version,
                metadata.description[:50] + "..." if len(metadata.description) > 50 else metadata.description,
                state,
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error listing plugins:[/red] {e}")
        raise typer.Exit(code=1)


@plugins_app.command("enable")
def plugins_enable(
    name: str = typer.Argument(..., help="Plugin name to enable"),
) -> None:
    """Enable a plugin."""
    try:
        from galehuntui.plugins import PluginManager
        
        manager = PluginManager()
        manager.discover()
        
        if manager.enable(name):
            console.print(f"[green]✓[/green] Plugin '{name}' enabled")
        else:
            console.print(f"[red]Error:[/red] Failed to enable plugin '{name}'")
            raise typer.Exit(code=1)
        
    except Exception as e:
        console.print(f"[red]Error enabling plugin:[/red] {e}")
        raise typer.Exit(code=1)


@plugins_app.command("disable")
def plugins_disable(
    name: str = typer.Argument(..., help="Plugin name to disable"),
) -> None:
    """Disable a plugin."""
    try:
        from galehuntui.plugins import PluginManager
        
        manager = PluginManager()
        manager.discover()
        
        if manager.disable(name):
            console.print(f"[green]✓[/green] Plugin '{name}' disabled")
        else:
            console.print(f"[red]Error:[/red] Failed to disable plugin '{name}'")
            raise typer.Exit(code=1)
        
    except Exception as e:
        console.print(f"[red]Error disabling plugin:[/red] {e}")
        raise typer.Exit(code=1)


@plugins_app.command("info")
def plugins_info(
    name: str = typer.Argument(..., help="Plugin name"),
) -> None:
    """Show detailed information about a plugin."""
    try:
        from galehuntui.plugins import PluginManager
        
        manager = PluginManager()
        manager.discover()
        
        info = manager.get_plugin_info(name)
        if not info:
            console.print(f"[red]Error:[/red] Plugin '{name}' not found")
            raise typer.Exit(code=1)
        
        plugin = info.plugin
        metadata = plugin.metadata
        
        console.print(Panel(
            f"[bold]Name:[/bold] {metadata.name}\n"
            f"[bold]Version:[/bold] {metadata.version}\n"
            f"[bold]Description:[/bold] {metadata.description}\n"
            f"[bold]Author:[/bold] {metadata.author or 'Unknown'}\n"
            f"[bold]Homepage:[/bold] {metadata.homepage or 'N/A'}\n"
            f"[bold]License:[/bold] {metadata.license or 'N/A'}\n"
            f"[bold]State:[/bold] {plugin.state.value}\n"
            f"[bold]Source:[/bold] {info.source}\n"
            f"[bold]Tool:[/bold] {plugin.tool_name}",
            title=f"Plugin: {name}",
        ))
        
    except Exception as e:
        console.print(f"[red]Error showing plugin info:[/red] {e}")
        raise typer.Exit(code=1)


@plugins_app.command("validate")
def plugins_validate(
    name: Optional[str] = typer.Argument(None, help="Plugin name (all if not specified)"),
) -> None:
    """Validate plugin(s) environment requirements."""
    try:
        from galehuntui.plugins import PluginManager
        
        manager = PluginManager()
        manager.discover()
        
        if name:
            valid, message = manager.validate(name)
            if valid:
                console.print(f"[green]✓[/green] Plugin '{name}' validated successfully")
            else:
                console.print(f"[red]✗[/red] Plugin '{name}' validation failed: {message}")
                raise typer.Exit(code=1)
        else:
            results = manager.validate_all()
            
            table = Table(title="Plugin Validation Results")
            table.add_column("Plugin", style="cyan")
            table.add_column("Valid", style="green")
            table.add_column("Message", style="yellow")
            
            all_valid = True
            for plugin_name, (valid, message) in results.items():
                status = "[green]✓[/green]" if valid else "[red]✗[/red]"
                table.add_row(plugin_name, status, message or "OK")
                if not valid:
                    all_valid = False
            
            console.print(table)
            
            if not all_valid:
                raise typer.Exit(code=1)
        
    except Exception as e:
        console.print(f"[red]Error validating plugins:[/red] {e}")
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
