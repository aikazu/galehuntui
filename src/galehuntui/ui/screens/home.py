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
from galehuntui.core.models import RunState, Severity, RunMetadata
from galehuntui.tools.installer import ToolInstaller

class HomeScreen(Screen):
    """The main dashboard screen of GaleHunTUI."""

    BINDINGS = [
        Binding("n", "new_run", "New Run", priority=True),
        Binding("t", "tools_manager", "Tools", priority=True),
        Binding("s", "settings", "Settings", priority=True),
        Binding("p", "profiles", "Profiles", priority=True),
        Binding("d", "delete_run", "Delete", priority=True),
        Binding("enter", "view_run", "View", priority=True),
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
        grid-columns: 3fr 1.2fr;
        grid-rows: auto auto 1fr;
        grid-gutter: 1;
        padding: 1;
    }

    #hero-panel {
        column-span: 2;
        height: 7;
        background: #1a1c29;
        border: solid #2e344d;
        padding: 1 2;
        layout: horizontal;
    }

    .hero-left {
        width: 3fr;
        height: 100%;
        content-align: left middle;
    }

    .hero-title {
        text-style: bold;
        color: #00f2ea;
    }

    .hero-subtitle {
        color: #64748b;
    }

    .hero-actions {
        width: 1fr;
        height: 100%;
    }

    .hero-actions Button {
        width: 100%;
        margin-bottom: 1;
    }

    /* Stats Panel */
    #stats-grid {
        column-span: 2;
        height: 7;
        layout: grid;
        grid-size: 4;
        grid-columns: 1fr 1fr 1fr 1fr;
        grid-rows: 1;
        grid-gutter: 1;
    }

    .stat-card {
        height: 100%;
        align: center middle;
        background: #1a1c29;
        border: solid #2e344d;
        padding: 1;
    }

    .stat-value {
        text-align: center;
        color: #00f2ea;
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
            with Horizontal(id="hero-panel"):
                with Vertical(classes="hero-left"):
                    yield Label("GaleHunTUI", classes="hero-title")
                    yield Label("Recon → Vulnerability Scanning → Targeted Injection → Reporting", classes="hero-subtitle")

            with Container(id="stats-grid"):
                yield self._make_stat_card("Total Runs", "-", value_id="stat_total_runs")
                yield self._make_stat_card("Subdomains", "-", value_id="stat_subdomains")
                yield self._make_stat_card("Live Hosts", "-", value_id="stat_live_hosts")
                yield self._make_stat_card("Findings", "-", value_id="stat_findings")

            # Main Content Area
            # Left: Recent Runs
            with Vertical(id="recent-runs-container"):
                yield Label("Recent Runs", classes="panel-header")
                yield DataTable(id="recent_runs_table", cursor_type="row")

            # Right: Actions & Status
            with Vertical(id="side-panel"):
                with Vertical(classes="status-box"):
                    yield Label("Quick Actions", classes="panel-header")
                    yield Button("New Run (N)", variant="primary", id="btn_new_run", classes="action-button")
                    yield Button("Tools Manager (T)", id="btn_tools", classes="action-button")
                    yield Button("Profiles (P)", id="btn_profiles", classes="action-button")
                    yield Button("Settings (S)", id="btn_settings", classes="action-button")

                with Vertical(classes="status-box"):
                    yield Label("Run Actions", classes="panel-header")
                    yield Button("View Selected", id="btn_view_run", classes="action-button")
                    yield Button("Delete Selected", variant="error", id="btn_delete_run", classes="action-button")

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

    def _get_step_output_count(self, run: RunMetadata, step_name: str) -> int:
        """Count items in a step output file."""
        try:
            output_path = run.artifacts_dir / step_name / "output.json"
            if not output_path.exists():
                return 0
            content = output_path.read_text().strip()
            if not content:
                return 0
            return len(content.split('\n'))
        except Exception:
            return 0

    def _categorize_findings(self, findings: list) -> dict:
        """Categorize findings into subdomain, live_domain, findings, and info."""
        counts = {
            "subdomain": 0,
            "live_domain": 0,
            "findings": 0,
            "info": 0,
        }
        
        for finding in findings:
            ftype = finding.type.lower() if finding.type else ""
            tool = finding.tool.lower() if finding.tool else ""
            
            is_subdomain = ftype in ("subdomain", "dns_record") or tool in ("subfinder", "dnsx")
            is_livedomain = ftype == "http_probe" or tool == "httpx"
            is_info = finding.severity == Severity.INFO
            
            if is_subdomain:
                counts["subdomain"] += 1
            elif is_livedomain:
                counts["live_domain"] += 1
            elif is_info:
                counts["info"] += 1
            else:
                counts["findings"] += 1
        
        return counts

    def on_mount(self) -> None:
        """Initialize data when screen is mounted."""
        table = self.query_one("#recent_runs_table", DataTable)
        table.add_columns("ID", "Target", "Profile", "Status", "Subdomain", "Live", "Findings", "Date")
        
        # Load real data in background
        _ = self._load_dashboard_data()

    def on_screen_resume(self) -> None:
        """Refresh data when returning to this screen."""
        _ = self._load_dashboard_data()

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
            total_subdomains = 0
            total_live_hosts = 0
            total_findings = 0
            
            with Database(db_path) as db:
                db.init_db()
                runs = db.list_runs(limit=10)
                
                all_runs = db.list_runs(limit=1000)
                total_runs_count = len(all_runs)
                
                for run in all_runs:
                    findings = db.get_findings_for_run(run.id)
                    counts = self._categorize_findings(findings)
                    total_subdomains += counts["subdomain"]
                    total_live_hosts += counts["live_domain"]
                    total_findings += counts["findings"]

            self.query_one("#stat_total_runs", Label).update(str(total_runs_count))
            self.query_one("#stat_subdomains", Label).update(str(total_subdomains))
            self.query_one("#stat_live_hosts", Label).update(str(total_live_hosts))
            self.query_one("#stat_findings", Label).update(str(total_findings))

            # Update Table
            table = self.query_one("#recent_runs_table", DataTable)
            table.clear()
            
            with Database(db_path) as db:
                for run in runs:
                    status = run.state.value.title()
                    
                    findings = db.get_findings_for_run(run.id)
                    counts = self._categorize_findings(findings)
                    
                    subdomain_count = counts["subdomain"]
                    live_count = counts["live_domain"]
                    finding_count = counts["findings"]
                    
                    findings_text = str(finding_count)
                    if finding_count > 0:
                        crit = sum(1 for f in findings if f.severity == Severity.CRITICAL and f.type.lower() not in ("subdomain", "dns_record", "http_probe") and f.tool.lower() not in ("subfinder", "dnsx", "httpx"))
                        high = sum(1 for f in findings if f.severity == Severity.HIGH and f.type.lower() not in ("subdomain", "dns_record", "http_probe") and f.tool.lower() not in ("subfinder", "dnsx", "httpx"))
                        if crit > 0:
                            findings_text = f"{finding_count} ({crit}C)"
                        elif high > 0:
                            findings_text = f"{finding_count} ({high}H)"

                    date_str = run.created_at.strftime("%Y-%m-%d %H:%M")
                    
                    table.add_row(
                        run.id[:8],
                        run.target,
                        run.profile.title(),
                        status,
                        str(subdomain_count) if subdomain_count > 0 else "-",
                        str(live_count) if live_count > 0 else "-",
                        findings_text if finding_count > 0 else "-",
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
        elif event.button.id == "btn_view_run":
            self.action_view_run()
        elif event.button.id == "btn_delete_run":
            self.action_delete_run()

    def _get_selected_run_id(self) -> Optional[str]:
        """Get the full run ID from the selected table row."""
        table = self.query_one("#recent_runs_table", DataTable)
        
        if table.row_count == 0:
            return None
        
        try:
            row_index = table.cursor_row
            if row_index is None or row_index < 0:
                return None
            
            row_data = table.get_row_at(row_index)
            if not row_data:
                return None
            
            short_id = str(row_data[0])
            
            data_dir = get_data_dir()
            db_path = data_dir / "galehuntui.db"
            
            with Database(db_path) as db:
                runs = db.list_runs(limit=100)
                for run in runs:
                    if run.id.startswith(short_id):
                        return run.id
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
        return None

    def action_view_run(self) -> None:
        """View the selected run details."""
        run_id = self._get_selected_run_id()
        if run_id:
            from galehuntui.ui.screens.run_detail import RunDetailScreen
            self.app.push_screen(RunDetailScreen(run_id))
        else:
            self.notify("Select a run first", severity="warning")

    def action_delete_run(self) -> None:
        """Delete the selected run after confirmation."""
        run_id = self._get_selected_run_id()
        if not run_id:
            self.notify("Select a run first", severity="warning")
            return
        
        self._confirm_delete(run_id)

    def _confirm_delete(self, run_id: str) -> None:
        """Show confirmation dialog for delete."""
        from textual.widgets import Button
        from textual.containers import Horizontal
        from textual.screen import ModalScreen
        
        class ConfirmDeleteScreen(ModalScreen[bool]):
            CSS = """
            ConfirmDeleteScreen {
                align: center middle;
            }
            
            #confirm-dialog {
                width: 50;
                height: 10;
                background: #1a1c29;
                border: solid #ff0055;
                padding: 1 2;
            }
            
            #confirm-buttons {
                margin-top: 1;
                align: center middle;
            }
            
            #confirm-buttons Button {
                margin: 0 1;
            }
            """
            
            def __init__(self, run_id: str):
                super().__init__()
                self.run_id = run_id
            
            def compose(self) -> ComposeResult:
                with Vertical(id="confirm-dialog"):
                    yield Label(f"Delete run {self.run_id[:8]}?")
                    yield Label("This action cannot be undone.")
                    with Horizontal(id="confirm-buttons"):
                        yield Button("Delete", variant="error", id="btn_confirm")
                        yield Button("Cancel", id="btn_cancel")
            
            def on_button_pressed(self, event: Button.Pressed) -> None:
                if event.button.id == "btn_confirm":
                    self.dismiss(True)
                else:
                    self.dismiss(False)
        
        def handle_delete_result(confirmed: bool) -> None:
            if confirmed:
                _ = self._do_delete(run_id)
        
        self.app.push_screen(ConfirmDeleteScreen(run_id), handle_delete_result)

    @work(exclusive=True)
    async def _do_delete(self, run_id: str) -> None:
        """Perform the actual deletion."""
        try:
            data_dir = get_data_dir()
            db_path = data_dir / "galehuntui.db"
            
            with Database(db_path) as db:
                success = db.delete_run(run_id)
                
            if success:
                self.notify(f"Run {run_id[:8]} deleted", severity="information")
                _ = self._load_dashboard_data()
            else:
                self.notify(f"Failed to delete run", severity="error")
                
        except Exception as e:
            self.notify(f"Delete failed: {e}", severity="error")
