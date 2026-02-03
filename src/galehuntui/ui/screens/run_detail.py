import logging
from pathlib import Path
from datetime import datetime
from typing import Set

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Label, Button, DataTable, RichLog, ProgressBar, 
    TabbedContent, TabPane, Static
)
from textual.containers import Container, Horizontal, Vertical
from textual import work

from galehuntui.storage.database import Database
from galehuntui.core.models import RunState, PipelineStep, Finding, Severity, RunMetadata
from galehuntui.core.constants import StepStatus
from galehuntui.core.config import get_data_dir

logger = logging.getLogger(__name__)

def count_output_items(output_path: Path | None) -> int:
    """Count items in a JSON lines output file."""
    if not output_path or not output_path.exists():
        return 0
    try:
        content = output_path.read_text().strip()
        if not content:
            return 0
        return len(content.split('\n'))
    except Exception:
        return 0

class RunDetailScreen(Screen):
    """Screen for monitoring a running scan or viewing a completed one."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("p", "toggle_pause", "Pause/Resume"),
        ("c", "cancel_run", "Cancel Run"),
        ("l", "focus_logs", "Logs"),
        ("s", "focus_subdomains", "Subdomains"),
        ("d", "focus_livedomain", "Live Domain"),
        ("f", "focus_findings", "Findings"),
        ("i", "focus_info", "Info"),
    ]

    CSS = """
    .run-detail-container {
        padding: 1;
    }

    /* Header Info Bar - Compact */
    .run-header {
        height: 3;
        background: $surface;
        border: solid $border;
        margin-bottom: 1;
    }
    
    .run-header-inner {
        padding: 0 2;
    }
    
    .header-item {
        width: auto;
        padding: 0 2;
        content-align: center middle;
    }
    
    .header-id {
        color: $text-muted;
    }
    
    .header-target {
        color: $text;
        text-style: bold;
    }
    
    .header-status {
        padding: 0 2;
        text-style: bold;
    }
    
    .header-status.running {
        color: $primary;
    }
    
    .header-status.completed {
        color: $success;
    }
    
    .header-status.failed, .header-status.cancelled {
        color: $error;
    }
    
    .header-status.paused {
        color: $warning;
    }
    
    .header-duration {
        color: $text-muted;
    }

    /* Stats Bar - Prominent */
    .stats-bar {
        height: 5;
        background: $surface;
        border: solid $border;
        margin-bottom: 1;
    }
    
    .stat-card {
        width: 1fr;
        height: 100%;
        content-align: center middle;
        border-right: solid $border;
    }
    
    .stat-card:last-child {
        border-right: none;
    }
    
    .stat-value {
        text-style: bold;
        color: $primary;
    }
    
    .stat-label {
        color: $text-muted;
    }

    /* Main Content Split */
    .main-split {
        height: 1fr;
    }

    /* Left Panel - Pipeline */
    .pipeline-panel {
        width: 35;
        height: 100%;
        background: $surface;
        border: solid $border;
        margin-right: 1;
    }
    
    .pipeline-header {
        height: 3;
        background: $panel;
        padding: 0 1;
        content-align: left middle;
        border-bottom: solid $border;
    }
    
    .pipeline-title {
        color: $primary;
        text-style: bold;
    }
    
    .pipeline-progress-container {
        height: 3;
        padding: 1;
        border-bottom: solid $border;
    }
    
    .steps-container {
        height: 1fr;
        padding: 0;
    }
    
    #steps-table {
        height: 100%;
        border: none;
        background: transparent;
    }
    
    #steps-table > .datatable--header {
        display: none;
    }
    
    .pipeline-controls {
        height: auto;
        padding: 1;
        border-top: solid $border;
    }
    
    .pipeline-controls Button {
        width: 100%;
        margin-bottom: 1;
        height: 3;
    }
    
    .pipeline-controls Button:last-child {
        margin-bottom: 0;
    }

    /* Right Panel - Logs/Findings */
    .content-panel {
        width: 1fr;
        height: 100%;
        border: solid $border;
    }
    
    #run-log {
        height: 100%;
        border: none;
        background: $background;
    }
    
    #findings-table {
        height: 100%;
        border: none;
    }
    
    /* Tab styling */
    TabbedContent {
        height: 100%;
    }
    
    TabPane {
        height: 100%;
        padding: 0;
    }
    
    ContentSwitcher {
        height: 100%;
    }
    """

    def __init__(self, run_id: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.run_id = run_id
        self._polling = False
        self._seen_finding_ids: Set[str] = set()
        self._last_step_states: dict[str, str] = {}
        self._db_path = get_data_dir() / "galehuntui.db"

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(classes="run-detail-container"):
            # Header Info Bar
            with Container(classes="run-header"):
                with Horizontal(classes="run-header-inner"):
                    yield Label("--", id="lbl-run-id", classes="header-item header-id")
                    yield Label("--", id="lbl-target", classes="header-item header-target")
                    yield Label("--", id="lbl-status", classes="header-item header-status")
                    yield Label("--", id="lbl-duration", classes="header-item header-duration")

            # Stats Bar
            with Horizontal(classes="stats-bar"):
                with Vertical(classes="stat-card"):
                    yield Label("0", id="val-subdomains", classes="stat-value")
                    yield Label("Subdomains", classes="stat-label")
                with Vertical(classes="stat-card"):
                    yield Label("0", id="val-live", classes="stat-value")
                    yield Label("Live Hosts", classes="stat-label")
                with Vertical(classes="stat-card"):
                    yield Label("0", id="val-findings", classes="stat-value")
                    yield Label("Findings", classes="stat-label")

            # Main Content
            with Horizontal(classes="main-split"):
                # Left: Pipeline
                with Vertical(classes="pipeline-panel"):
                    with Container(classes="pipeline-header"):
                        yield Label("Pipeline", classes="pipeline-title")
                    with Container(classes="pipeline-progress-container"):
                        yield ProgressBar(total=100, show_eta=False, id="run-progress")
                    with Container(classes="steps-container"):
                        yield DataTable(id="steps-table")
                    with Vertical(classes="pipeline-controls"):
                        yield Button("Pause", variant="warning", id="btn-pause")
                        yield Button("Cancel", variant="error", id="btn-cancel")
                        yield Button("Export", variant="primary", id="btn-export")

                # Right: Logs/Findings with 5 tabs
                with Container(classes="content-panel"):
                    with TabbedContent():
                        with TabPane("Live Logs", id="tab-logs"):
                            yield RichLog(highlight=True, markup=True, id="run-log")
                        with TabPane("Subdomain (0)", id="tab-subdomain"):
                            yield DataTable(id="subdomain-table")
                        with TabPane("Live Domain (0)", id="tab-livedomain"):
                            yield DataTable(id="livedomain-table")
                        with TabPane("Findings (0)", id="tab-findings"):
                            yield DataTable(id="findings-table")
                        with TabPane("Info (0)", id="tab-info"):
                            yield DataTable(id="info-table")
        
        yield Footer()

    def on_mount(self) -> None:
        """Initialize widgets and start data loading."""
        if not self.run_id:
            self.run_id = getattr(self.app, 'current_run_id', None)
        
        if not self.run_id:
            self.notify("No run selected", severity="error")
            self.app.pop_screen()
            return

        # Setup Findings Table (real vulnerabilities - not INFO)
        findings_table = self.query_one("#findings-table", DataTable)
        findings_table.add_columns("Severity", "Type", "Host", "Tool")
        findings_table.cursor_type = "row"

        # Setup Subdomain Table (subdomain + dnsx results)
        subdomain_table = self.query_one("#subdomain-table", DataTable)
        subdomain_table.add_columns("Host", "Tool")
        subdomain_table.cursor_type = "row"

        # Setup Live Domain Table (httpx results)
        livedomain_table = self.query_one("#livedomain-table", DataTable)
        livedomain_table.add_columns("Host", "Tool")
        livedomain_table.cursor_type = "row"

        # Setup Info Table (other INFO severity items)
        info_table = self.query_one("#info-table", DataTable)
        info_table.add_columns("Type", "Host", "Tool")
        info_table.cursor_type = "row"

        # Setup Steps Table (single column, no header)
        steps_table = self.query_one("#steps-table", DataTable)
        steps_table.add_columns("Step")
        steps_table.show_header = False
        
        # Start loading data
        _ = self._load_run_data()

    @work(exclusive=True)
    async def _load_run_data(self) -> None:
        """Initial data load from database."""
        if not self.run_id:
            return

        try:
            db = Database(self._db_path)
            
            run = db.get_run(self.run_id)
            if not run:
                self.notify("Run not found in database", severity="error")
                self.app.pop_screen()
                return

            steps = db.get_steps(self.run_id)
            findings = db.get_findings_for_run(self.run_id)
            db.close()

            # Update UI
            self._update_header(run)
            self._update_stats(steps, len(findings))
            self._update_steps(steps)
            self._update_findings(findings)
            self._update_progress(run)
            self._log_initial(run)

            # Start polling if active
            if run.state in (RunState.RUNNING, RunState.PENDING, RunState.PAUSED):
                self._start_polling()

        except Exception as e:
            logger.exception(f"Error loading run data: {e}")
            self.notify(f"Error loading run: {e}", severity="error")

    def _start_polling(self) -> None:
        """Start the polling interval."""
        if not self._polling:
            self._polling = True
            self.set_interval(2.0, self._poll_updates)

    async def _poll_updates(self) -> None:
        """Poll database for updates."""
        if not self.run_id or not self._polling:
            return
        try:
            _ = self._fetch_updates()
        except Exception as e:
            logger.debug(f"Polling error: {e}")

    @work(exclusive=True)
    async def _fetch_updates(self) -> None:
        """Worker to fetch updates."""
        try:
            if not self.run_id:
                return

            db = Database(self._db_path)
            run = db.get_run(self.run_id)
            
            if run:
                if run.state in (RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED):
                    self._polling = False
                
                self._update_header(run)
                self._update_progress(run)

                steps = db.get_steps(self.run_id)
                findings = db.get_findings_for_run(self.run_id)
                
                self._update_stats(steps, len(findings))
                self._update_steps(steps)
                self._update_findings(findings)

            db.close()
        except Exception as e:
            logger.warning(f"Error fetching updates: {e}")

    def _update_header(self, run: RunMetadata) -> None:
        """Update header info bar."""
        self.query_one("#lbl-run-id", Label).update(run.id[:12])
        self.query_one("#lbl-target", Label).update(run.target)
        
        status_label = self.query_one("#lbl-status", Label)
        status_label.update(run.state.name)
        status_label.set_classes(f"header-item header-status {run.state.name.lower()}")
        
        # Duration
        duration = "--:--:--"
        if run.started_at:
            end_time = run.completed_at or datetime.now()
            delta = end_time - run.started_at
            total_seconds = int(delta.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration = f"{hours:02}:{minutes:02}:{seconds:02}"
        self.query_one("#lbl-duration", Label).update(duration)
        
        # Buttons
        pause_btn = self.query_one("#btn-pause", Button)
        if run.state == RunState.RUNNING:
            pause_btn.label = "Pause"
            pause_btn.variant = "warning"
            pause_btn.disabled = False
        elif run.state == RunState.PAUSED:
            pause_btn.label = "Resume"
            pause_btn.variant = "success"
            pause_btn.disabled = False
        else:
            pause_btn.disabled = True
            
        self.query_one("#btn-cancel", Button).disabled = not run.is_active

    def _update_progress(self, run: RunMetadata) -> None:
        """Update progress bar."""
        progress_bar = self.query_one("#run-progress", ProgressBar)
        if run.total_steps > 0:
            pct = (run.completed_steps / run.total_steps) * 100
            progress_bar.update(progress=pct)

    def _update_stats(self, steps: list[PipelineStep], findings_count: int) -> None:
        """Update stats bar."""
        subdomains = 0
        live_hosts = 0
        
        for step in steps:
            if step.output_path:
                count = count_output_items(step.output_path)
                if step.name == "subdomain_enumeration":
                    subdomains = count
                elif step.name == "http_probing":
                    live_hosts = count
        
        self.query_one("#val-subdomains", Label).update(str(subdomains))
        self.query_one("#val-live", Label).update(str(live_hosts))
        self.query_one("#val-findings", Label).update(str(findings_count))

    def _update_steps(self, steps: list[PipelineStep]) -> None:
        """Update steps table."""
        table = self.query_one("#steps-table", DataTable)
        log = self.query_one("#run-log", RichLog)
        
        # Status icons
        icons = {
            StepStatus.COMPLETED: ("✓", "green"),
            StepStatus.RUNNING: ("●", "cyan"),
            StepStatus.FAILED: ("✗", "red"),
            StepStatus.SKIPPED: ("○", "dim"),
            StepStatus.PENDING: ("○", "dim"),
        }
        
        for step in steps:
            icon, color = icons.get(step.status, ("○", "dim"))
            
            # Format: icon + name + optional duration
            if step.status == StepStatus.COMPLETED and step.duration:
                display = f"[{color}]{icon}[/] {step.name} [dim]({step.duration:.0f}s)[/]"
            elif step.status == StepStatus.RUNNING:
                display = f"[{color}]{icon}[/] [bold]{step.name}[/] [dim]...[/]"
            else:
                display = f"[{color}]{icon}[/] {step.name}"
            
            row_key = f"step-{step.name}"
            
            # Log state changes
            prev = self._last_step_states.get(step.name)
            if prev != step.status.name:
                self._last_step_states[step.name] = step.status.name
                if step.status == StepStatus.RUNNING:
                    log.write(f"[cyan]▶[/] Starting [bold]{step.name}[/]")
                elif step.status == StepStatus.COMPLETED:
                    dur = f" ({step.duration:.0f}s)" if step.duration else ""
                    log.write(f"[green]✓[/] Completed [bold]{step.name}[/]{dur}")
                elif step.status == StepStatus.FAILED:
                    log.write(f"[red]✗[/] Failed [bold]{step.name}[/]")
                    if step.error_message:
                        log.write(f"  [dim]{step.error_message}[/]")

            # Update or add row
            try:
                table.get_row_index(row_key)
                table.update_cell(row_key, "Step", display)
            except Exception:
                table.add_row(display, key=row_key)

    def _update_findings(self, findings: list[Finding]) -> None:
        """Update findings tables - categorized into Subdomain, Live Domain, Findings, and Info tabs."""
        findings_table = self.query_one("#findings-table", DataTable)
        subdomain_table = self.query_one("#subdomain-table", DataTable)
        livedomain_table = self.query_one("#livedomain-table", DataTable)
        info_table = self.query_one("#info-table", DataTable)
        log = self.query_one("#run-log", RichLog)
        
        colors = {
            Severity.CRITICAL: "red",
            Severity.HIGH: "orange1",
            Severity.MEDIUM: "yellow",
            Severity.LOW: "blue",
            Severity.INFO: "dim",
        }

        subdomain_count = 0
        livedomain_count = 0
        findings_count = 0
        info_count = 0

        for finding in findings:
            ftype = finding.type.lower()
            tool = finding.tool.lower() if finding.tool else ""
            
            is_subdomain = ftype in ("subdomain", "dns_record") or tool in ("subfinder", "dnsx")
            is_livedomain = ftype == "http_probe" or tool == "httpx"
            is_info = finding.severity == Severity.INFO
            
            if is_subdomain:
                subdomain_count += 1
                if finding.id not in self._seen_finding_ids:
                    self._seen_finding_ids.add(finding.id)
                    subdomain_table.add_row(
                        finding.host[:60],
                        finding.tool,
                        key=finding.id
                    )
            elif is_livedomain:
                livedomain_count += 1
                if finding.id not in self._seen_finding_ids:
                    self._seen_finding_ids.add(finding.id)
                    livedomain_table.add_row(
                        finding.host[:60],
                        finding.tool,
                        key=finding.id
                    )
            elif is_info:
                info_count += 1
                if finding.id not in self._seen_finding_ids:
                    self._seen_finding_ids.add(finding.id)
                    info_table.add_row(
                        finding.type[:30],
                        finding.host[:50],
                        finding.tool,
                        key=finding.id
                    )
            else:
                findings_count += 1
                if finding.id not in self._seen_finding_ids:
                    self._seen_finding_ids.add(finding.id)
                    color = colors.get(finding.severity, "white")
                    sev = f"[{color}]{finding.severity.value.upper()}[/]"
                    
                    findings_table.add_row(
                        sev,
                        finding.type[:30],
                        finding.host[:40],
                        finding.tool,
                        key=finding.id
                    )
                    
                    if finding.severity in (Severity.CRITICAL, Severity.HIGH):
                        log.write(f"[{color}]⚠[/] {finding.severity.value.upper()}: {finding.type} @ {finding.host}")

        try:
            from textual.widgets import TabPane
            self.query_one("#tab-subdomain", TabPane).update(f"Subdomain ({subdomain_count})")
            self.query_one("#tab-livedomain", TabPane).update(f"Live Domain ({livedomain_count})")
            self.query_one("#tab-findings", TabPane).update(f"Findings ({findings_count})")
            self.query_one("#tab-info", TabPane).update(f"Info ({info_count})")
        except Exception:
            pass

    def _log_initial(self, run: RunMetadata) -> None:
        """Log initial state."""
        log = self.query_one("#run-log", RichLog)
        log.write(f"[dim]─── Run Monitor ───[/]")
        log.write(f"Target: [bold]{run.target}[/]")
        log.write(f"Profile: {run.profile}")
        log.write(f"State: {run.state.name}")
        log.write("")
        
    def action_toggle_pause(self) -> None:
        self.notify("Control commands not yet implemented", severity="warning")

    def action_cancel_run(self) -> None:
        self.notify("Sending cancel signal...", severity="warning")

    def action_focus_logs(self) -> None:
        self.query_one("#run-log").focus()

    def action_focus_subdomains(self) -> None:
        self.query_one("#subdomain-table").focus()

    def action_focus_livedomain(self) -> None:
        self.query_one("#livedomain-table").focus()

    def action_focus_findings(self) -> None:
        self.query_one("#findings-table").focus()

    def action_focus_info(self) -> None:
        self.query_one("#info-table").focus()
