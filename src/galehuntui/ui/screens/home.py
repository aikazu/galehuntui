from datetime import datetime
from pathlib import Path
from typing import Optional

from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, DataTable, Static, Label, Digits
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding

from galehuntui.storage.database import Database
from galehuntui.core.config import get_data_dir
from galehuntui.core.models import RunState, Severity
from galehuntui.tools.installer import ToolInstaller

class HomeScreen(Screen):
    """The main dashboard screen of GaleHunTUI."""

    BINDINGS = [
        Binding("n", "new_run", "New Run", priority=True),
        Binding("t", "tools_manager", "Tools", priority=True),
        Binding("s", "settings", "Settings", priority=True),
        Binding("p", "profiles", "Profiles", priority=True),
        # Q is global in app.py for Quit
    ]

    CSS = """
    HomeScreen {
        align: center middle;
    }

    #home-container {
        width: 100%;
        height: 100%;
        layout: grid;
        grid-size: 2;
        grid-columns: 3fr 1fr;
        grid-rows: auto 1fr;
        grid-gutter: 1;
        padding: 1;
    }

    /* Stats Panel */
    #stats-panel {
        column-span: 2;
        height: 7;
        background: #1a1c29;
        border: solid #2e344d;
        layout: horizontal;
        padding: 0 1;
        margin-bottom: 1;
    }

    .stat-card {
        width: 1fr;
        height: 100%;
        align: center middle;
        border-right: solid #0f111a;
    }
    
    .stat-card:last-of-type {
        border-right: none;
    }

    .stat-value {
        text-align: center;
        color: #ff0055;
        text-style: bold;
        width: 100%;
        content-align: center middle;
    }

    .stat-label {
        text-align: center;
        color: #64748b;
        width: 100%;
    }

    /* Recent Runs Table */
    #recent-runs-container {
        height: 100%;
        border: solid #2e344d;
        background: #0f111a;
        row-span: 1;
    }
    
    DataTable {
        height: 100%;
        background: #0f111a;
        border: none;
    }
    
    DataTable > .datatable--header {
        background: #1a1c29;
        color: #00f2ea;
        text-style: bold;
    }

    /* Side Panel */
    #side-panel {
        height: 100%;
        layout: vertical;
    }

    .panel-header {
        background: #1a1c29;
        color: #00f2ea;
        text-style: bold;
        padding: 0 1;
        height: 1;
        margin-bottom: 1;
        width: 100%;
    }

    .action-button {
        width: 100%;
        margin-bottom: 1;
    }

    .status-box {
        background: #1a1c29;
        border: solid #2e344d;
        padding: 1;
        height: auto;
        margin-bottom: 1;
    }
    
    .status-row {
        layout: horizontal;
        height: 1;
        margin-bottom: 0;
        width: 100%;
    }
    
    .status-dot {
        color: #00ff9d;
        margin-right: 1;
    }
    
    .status-text {
        color: #64748b;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(id="home-container"):
            # Top Stats Row
            with Horizontal(id="stats-panel"):
                yield self._make_stat_card("Total Runs", "-", value_id="stat_total_runs")
                yield self._make_stat_card("Critical Findings", "-", value_id="stat_critical_findings")
                yield self._make_stat_card("Tools Installed", "-", value_id="stat_tools_installed")
                yield self._make_stat_card("Last Scan", "-", value_id="stat_last_scan")

            # Main Content Area
            # Left: Recent Runs
            with Vertical(id="recent-runs-container"):
                yield Label("Recent Runs", classes="panel-header")
                yield DataTable(id="recent_runs_table", cursor_type="row")

            # Right: Actions & Status
            with Vertical(id="side-panel"):
                # Quick Actions
                with Vertical(classes="status-box"):
                    yield Label("Quick Actions", classes="panel-header")
                    yield Button("New Run (N)", variant="primary", id="btn_new_run", classes="action-button")
                    yield Button("Tools Manager (T)", id="btn_tools", classes="action-button")
                    yield Button("Profiles (P)", id="btn_profiles", classes="action-button")
                    yield Button("Settings (S)", id="btn_settings", classes="action-button")

                # System Status
                with Vertical(classes="status-box"):
                    yield Label("System Status", classes="panel-header")
                    yield self._make_status_row("Database", "Checking...", id="status_db")
                    yield self._make_status_row("Docker", "Checking...", id="status_docker")
                    yield self._make_status_row("Network", "Online", id="status_network")

        yield Footer()

    def _make_stat_card(self, label: str, value: str, value_id: Optional[str] = None) -> Vertical:
        """Create a stat card with value and label."""
        # Using Label for value instead of Digits for better layout control in this grid
        return Vertical(
            Label(value, classes="stat-value", id=value_id),
            Label(label, classes="stat-label"),
            classes="stat-card"
        )

    def _make_status_row(self, label: str, status: str, id: Optional[str] = None) -> Horizontal:
        """Create a status row with a dot and text."""
        return Horizontal(
            Label("●", classes="status-dot"),
            Label(f"{label}: {status}", classes="status-text", id=id),
            classes="status-row"
        )

    def on_mount(self) -> None:
        """Initialize data when screen is mounted."""
        table = self.query_one("#recent_runs_table", DataTable)
        table.add_columns("ID", "Target", "Profile", "Status", "Findings", "Date")
        
        # Load real data in background
        self._load_dashboard_data()

    @work(exclusive=True)
    async def _load_dashboard_data(self) -> None:
        """Load dashboard data from database in background."""
        try:
            data_dir = get_data_dir()
            db_path = data_dir / "galehuntui.db"
            
            # Update DB Status
            db_status_label = self.query_one("#status_db", Label)
            if db_path.exists():
                db_status_label.update("Database: Connected")
                db_status_label.styles.color = "green"
            else:
                db_status_label.update("Database: Initializing")
            
            # Check Docker (simple check)
            # In a real scenario, we might want to check if docker socket exists or run a command
            # For now, we'll check if docker command is available
            import shutil
            docker_path = shutil.which("docker")
            docker_status_label = self.query_one("#status_docker", Label)
            if docker_path:
                docker_status_label.update("Docker: Available")
                # docker_status_label.styles.color = "green" # Default text color is fine
            else:
                docker_status_label.update("Docker: Not Found")
                docker_status_label.styles.color = "red"

            runs = []
            total_runs_count = 0
            critical_findings_count = 0
            
            with Database(db_path) as db:
                db.init_db()
                # Get recent runs
                runs = db.list_runs(limit=10)
                
                # Get all runs count (for stats) - naive approach, list_runs with higher limit
                # Ideally DB should have count method, but we work with what we have
                all_runs = db.list_runs(limit=1000)
                total_runs_count = len(all_runs)
                
                # Calculate critical findings across all runs
                for run in all_runs:
                    if Severity.CRITICAL.value in run.findings_by_severity:
                        critical_findings_count += run.findings_by_severity[Severity.CRITICAL.value]

            # Update Stats
            self.query_one("#stat_total_runs", Label).update(str(total_runs_count))
            self.query_one("#stat_critical_findings", Label).update(str(critical_findings_count))
            
            # Check Tools
            installer = ToolInstaller(data_dir / "tools")
            try:
                registry = installer.load_registry()
                all_tools = registry.get("tools", {})
                installed_tools = sum(1 for t in all_tools if installer.verify_tool(t))
                total_tools = len(all_tools)
                self.query_one("#stat_tools_installed", Label).update(f"{installed_tools}/{total_tools}")
            except Exception as e:
                self.query_one("#stat_tools_installed", Label).update("Error")
            
            # Last Scan Time
            if runs:
                last_run = runs[0]
                time_diff = datetime.now() - last_run.created_at
                
                if time_diff.days > 0:
                    time_str = f"{time_diff.days}d ago"
                elif time_diff.seconds >= 3600:
                    time_str = f"{time_diff.seconds // 3600}h ago"
                elif time_diff.seconds >= 60:
                    time_str = f"{time_diff.seconds // 60}m ago"
                else:
                    time_str = "Just now"
                    
                self.query_one("#stat_last_scan", Label).update(time_str)
            else:
                self.query_one("#stat_last_scan", Label).update("Never")

            # Update Table
            table = self.query_one("#recent_runs_table", DataTable)
            table.clear()
            
            for run in runs:
                # Format Status
                status = run.state.value.title()
                
                # Format Findings Summary
                findings_summary = []
                if run.findings_by_severity:
                    crit = run.findings_by_severity.get(Severity.CRITICAL.value, 0)
                    high = run.findings_by_severity.get(Severity.HIGH.value, 0)
                    med = run.findings_by_severity.get(Severity.MEDIUM.value, 0)
                    
                    if crit > 0:
                        findings_summary.append(f"{crit} Crit")
                    if high > 0:
                        findings_summary.append(f"{high} High")
                    if med > 0:
                        findings_summary.append(f"{med} Med")
                        
                    summary_text = ", ".join(findings_summary) if findings_summary else f"{run.total_findings} Issues"
                else:
                    summary_text = "0 Issues" if run.total_findings == 0 else f"{run.total_findings} Issues"
                
                if not summary_text:
                    summary_text = "-"

                # Format Date
                date_str = run.created_at.strftime("%Y-%m-%d %H:%M")
                
                # Add row
                table.add_row(
                    run.id[:8], # Short ID
                    run.target,
                    run.profile.title(),
                    status,
                    summary_text,
                    date_str
                )

        except Exception as e:
            self.notify(f"Failed to load dashboard data: {e}", severity="error")


    def action_new_run(self) -> None:
        self.app.push_screen("new_run")

    def action_tools_manager(self) -> None:
        self.app.push_screen("tools_manager")

    def action_settings(self) -> None:
        self.app.push_screen("settings")

    def action_profiles(self) -> None:
        self.app.push_screen("profiles")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_new_run":
            self.action_new_run()
        elif event.button.id == "btn_tools":
            self.action_tools_manager()
        elif event.button.id == "btn_profiles":
            self.action_profiles()
        elif event.button.id == "btn_settings":
            self.action_settings()
