import logging
from pathlib import Path
from datetime import datetime
from typing import Set

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Label, Button, DataTable, RichLog, ProgressBar, 
    TabbedContent, TabPane
)
from textual.containers import Container, Horizontal
from textual import work

from galehuntui.storage.database import Database
from galehuntui.core.models import RunState, PipelineStep, Finding, Severity, RunMetadata
from galehuntui.core.constants import StepStatus

logger = logging.getLogger(__name__)

def get_data_dir() -> Path:
    """Get the data directory path."""
    return Path.home() / ".local" / "share" / "galehuntui"

class RunDetailScreen(Screen):
    """Screen for monitoring a running scan or viewing a completed one."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("p", "toggle_pause", "Pause/Resume"),
        ("c", "cancel_run", "Cancel Run"),
    ]

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
            # Top Info Panel
            with Horizontal(classes="run-info-bar"):
                yield Label("Run ID: --", classes="info-label", id="label-run-id")
                yield Label("Target: --", classes="info-label", id="label-target")
                yield Label("Status: --", classes="status-badge", id="run-status")
                yield Label("Duration: --", classes="info-label", id="run-duration")

            with Horizontal(classes="split-view"):
                with Container(classes="sidebar-panel"):
                    yield Label("Pipeline", classes="section-title")
                    yield ProgressBar(total=100, show_eta=True, classes="pipeline-progress", id="run-progress")
                    yield DataTable(id="steps-table")

                    with Container(classes="sidebar-controls"):
                        yield Button("Pause Run", variant="warning", id="btn-pause", classes="control-btn")
                        yield Button("Cancel Run", variant="error", id="btn-cancel", classes="control-btn")
                        yield Button("Export Report", variant="primary", id="btn-export", classes="control-btn")

                with Container(classes="main-panel"):
                    with TabbedContent():
                        with TabPane("Live Logs", id="tab-logs"):
                            yield RichLog(highlight=True, markup=True, id="run-log")

                        with TabPane("Findings", id="tab-findings"):
                            yield DataTable(id="findings-table")
        
        yield Footer()

    def on_mount(self) -> None:
        """Initialize widgets and start data loading."""
        # Check for run_id from init or app
        if not self.run_id:
            self.run_id = getattr(self.app, 'current_run_id', None)
        
        if not self.run_id:
            self.notify("No run selected", severity="error")
            self.app.pop_screen()
            return

        # Setup Findings Table
        findings_table = self.query_one("#findings-table", DataTable)
        findings_table.add_columns("ID", "Severity", "Type", "Host", "Confidence")
        findings_table.cursor_type = "row"

        # Setup Steps Table
        steps_table = self.query_one("#steps-table", DataTable)
        steps_table.add_columns("Step", "Status", "Duration")
        
        # Start loading data
        _ = self._load_run_data()

    @work(exclusive=True)
    async def _load_run_data(self) -> None:
        """Initial data load from database."""
        if not self.run_id:
            return

        try:
            db = Database(self._db_path)
            # No explicit init_db() needed here as app should have done it, 
            # but connecting handles the connection.
            
            run = db.get_run(self.run_id)
            if not run:
                self.notify("Run not found in database", severity="error")
                self.app.pop_screen()
                return

            steps = db.get_steps(self.run_id)
            findings = db.get_findings_for_run(self.run_id)
            db.close()

            # Update UI components directly (safe within @work async context)
            self._update_run_header(run)
            self._update_steps_table(steps)
            self._update_findings_table(findings)
            self._update_progress(run)
            self._log_initial_state(run)
            self._log_step_errors(steps)

            # Start polling if active
            if run.state in (RunState.RUNNING, RunState.PENDING, RunState.PAUSED):
                self._start_polling()

        except Exception as e:
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
            # We can't use @work for the interval callback directly as it spawns too many workers
            # But we should run DB ops in a worker. 
            # Ideally set_interval calls a method that calls a worker.
            _ = self._fetch_updates_worker()
        except Exception as e:
            logger.debug(f"Polling error (non-fatal): {e}")

    @work(exclusive=True)
    async def _fetch_updates_worker(self) -> None:
        """Worker to fetch updates."""
        try:
            if not self.run_id:
                return

            db = Database(self._db_path)
            run = db.get_run(self.run_id)
            
            if run:
                # Check if we should stop polling
                if run.state in (RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED):
                    self._polling = False
                
                # Update UI (we're in the same thread with @work)
                self._update_run_header(run)
                self._update_progress(run)

                steps = db.get_steps(self.run_id)
                self._update_steps_table(steps)

                findings = db.get_findings_for_run(self.run_id)
                self._update_findings_table(findings)

            db.close()
        except Exception as e:
            logger.warning(f"Error fetching updates for run {self.run_id}: {e}")

    def _update_run_header(self, run: RunMetadata) -> None:
        """Update the top info bar."""
        self.query_one("#label-run-id", Label).update(f"Run ID: {run.id}")
        self.query_one("#label-target", Label).update(f"Target: {run.target}")
        
        status_label = self.query_one("#run-status", Label)
        status_label.update(f"Status: {run.state.name}")
        
        # Update status classes
        status_label.set_classes("status-badge")
        if run.state == RunState.RUNNING:
            status_label.add_class("running")
        elif run.state == RunState.COMPLETED:
            status_label.add_class("success")
        elif run.state in (RunState.FAILED, RunState.CANCELLED):
            status_label.add_class("error")
        elif run.state == RunState.PAUSED:
            status_label.add_class("warning")
            
        # Update duration
        duration = "00:00:00"
        if run.started_at:
            end_time = run.completed_at or datetime.now()
            delta = end_time - run.started_at
            # Format delta manually to avoid days component if possible or just use str
            total_seconds = int(delta.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            duration = f"{hours:02}:{minutes:02}:{seconds:02}"
            
        self.query_one("#run-duration", Label).update(f"Duration: {duration}")
        
        # Update buttons state based on run state
        pause_btn = self.query_one("#btn-pause", Button)
        if run.state == RunState.RUNNING:
            pause_btn.label = "Pause Run"
            pause_btn.variant = "warning"
            pause_btn.disabled = False
        elif run.state == RunState.PAUSED:
            pause_btn.label = "Resume Run"
            pause_btn.variant = "success"
            pause_btn.disabled = False
        else:
            pause_btn.disabled = True
            
        cancel_btn = self.query_one("#btn-cancel", Button)
        cancel_btn.disabled = not run.is_active

    def _update_progress(self, run: RunMetadata) -> None:
        """Update progress bar."""
        progress_bar = self.query_one("#run-progress", ProgressBar)
        if run.total_steps > 0:
            pct = (run.completed_steps / run.total_steps) * 100
            progress_bar.update(progress=pct)
            
            # If we know the current running step, we could show it in message
            # but ProgressBar doesn't support text message easily in standard API 
            # without custom renderable, so just percentage is fine.

    def _update_steps_table(self, steps: list[PipelineStep]) -> None:
        """Update the steps table."""
        table = self.query_one("#steps-table", DataTable)
        log = self.query_one("#run-log", RichLog)
        
        for step in steps:
            duration_str = "--"
            if step.duration:
                duration_str = f"{step.duration:.1f}s"
            elif step.status == StepStatus.RUNNING and step.started_at:
                delta = (datetime.now() - step.started_at).total_seconds()
                duration_str = f"{delta:.1f}s..."

            status_styled = str(step.status.name)
            if step.status == StepStatus.COMPLETED:
                status_styled = f"[green]{step.status.name}[/]"
            elif step.status == StepStatus.RUNNING:
                status_styled = f"[blue]{step.status.name}[/]"
            elif step.status == StepStatus.FAILED:
                status_styled = f"[red]{step.status.name}[/]"
            elif step.status == StepStatus.SKIPPED:
                status_styled = f"[dim]{step.status.name}[/]"

            row_key = f"step-{step.name}"
            
            # Log state changes
            prev_status = self._last_step_states.get(step.name)
            if prev_status != step.status.name:
                self._last_step_states[step.name] = step.status.name
                if step.status == StepStatus.RUNNING:
                    log.write(f"[blue]INFO[/] Started step: [bold]{step.name}[/]")
                elif step.status == StepStatus.COMPLETED:
                    log.write(f"[green]SUCCESS[/] Completed step: [bold]{step.name}[/] ({duration_str})")
                elif step.status == StepStatus.FAILED:
                    log.write(f"[red]ERROR[/] Failed step: [bold]{step.name}[/]")
                    if step.error_message:
                        log.write(f"[red]Details[/]: {step.error_message}")

            # Check if row exists by trying to get its index
            try:
                table.get_row_index(row_key)
                # Row exists, update it
                table.update_cell(row_key, "Status", status_styled)
                table.update_cell(row_key, "Duration", duration_str)
            except Exception:
                # Row doesn't exist, add it
                table.add_row(
                    step.name, 
                    status_styled, 
                    duration_str, 
                    key=row_key
                )

    def _update_findings_table(self, findings: list[Finding]) -> None:
        """Update findings table with new entries."""
        table = self.query_one("#findings-table", DataTable)
        log = self.query_one("#run-log", RichLog)
        
        color_map = {
            Severity.CRITICAL: "red",
            Severity.HIGH: "orange1",
            Severity.MEDIUM: "yellow",
            Severity.LOW: "blue",
            Severity.INFO: "white"
        }

        for finding in findings:
            if finding.id not in self._seen_finding_ids:
                self._seen_finding_ids.add(finding.id)
                
                color = color_map.get(finding.severity, "white")
                sev_display = f"[{color}]{finding.severity.value.upper()}[/]"
                
                table.add_row(
                    finding.id[:8], # Short ID
                    sev_display,
                    finding.type,
                    finding.host,
                    finding.confidence.value,
                    key=finding.id
                )
                
                # Log high severity findings
                if finding.severity in (Severity.CRITICAL, Severity.HIGH):
                    log.write(f"[{color}]ALERT[/] Found {finding.severity.value.upper()} vulnerability: {finding.type} on {finding.host}")
                    self.notify(f"New {finding.severity.value} finding: {finding.type}")

    def _log_initial_state(self, run: RunMetadata) -> None:
        """Log initial run info."""
        log = self.query_one("#run-log", RichLog)
        log.write(f"[green]INFO[/] Monitor attached to run {run.id}")
        log.write(f"[blue]INFO[/] Target: {run.target}")
        log.write(f"[blue]INFO[/] Profile: {run.profile}")
        log.write(f"[blue]INFO[/] State: {run.state.name}")
        
        if run.state == RunState.FAILED:
            log.write(f"[red]ERROR[/] Run failed")
        elif run.state == RunState.COMPLETED:
            log.write(f"[green]SUCCESS[/] Run completed with {run.total_findings} findings")
        elif run.state == RunState.RUNNING:
            log.write(f"[blue]INFO[/] Run is currently in progress...")
        elif run.state == RunState.PENDING:
            log.write(f"[yellow]INFO[/] Run is pending start...")

    def _log_step_errors(self, steps: list[PipelineStep]) -> None:
        """Log step status to the live log."""
        log = self.query_one("#run-log", RichLog)
        for step in steps:
            if step.status == StepStatus.COMPLETED:
                duration = f"{step.duration:.1f}s" if step.duration else "--"
                log.write(f"[green]COMPLETED[/] Step [bold]{step.name}[/] ({duration}) - {step.findings_count} items")
                if step.output_path and step.output_path.exists():
                    try:
                        content = step.output_path.read_text()
                        lines = content.strip().split('\n')[:5]
                        for line in lines:
                            log.write(f"  [dim]{line[:80]}[/]")
                        if len(content.strip().split('\n')) > 5:
                            log.write(f"  [dim]... and more[/]")
                    except Exception:
                        pass
            elif step.status == StepStatus.FAILED:
                log.write(f"[red]FAILED[/] Step [bold]{step.name}[/]: {step.error_message or 'Unknown error'}")
            elif step.status == StepStatus.SKIPPED:
                log.write(f"[yellow]SKIPPED[/] Step [bold]{step.name}[/]: {step.error_message or 'Dependencies not met'}")
            elif step.status == StepStatus.RUNNING:
                log.write(f"[blue]RUNNING[/] Step [bold]{step.name}[/]...")
        
    def action_toggle_pause(self) -> None:
        """Pause or resume the run."""
        # For MVP without direct Orchestrator access, we just update local UI state 
        # and notify. In a real app, this would send a command to the daemon/backend.
        # Since I can't easily reach the backend process from here without an API or shared object,
        # I will leave a TODO note and show notification.
        
        # Attempt to check if we can update DB state directly as a signal
        # (Though Orchestrator might overwrite it, it's a way to signal if Orchestrator watches DB)
        
        self.notify("Control commands not yet wired to backend daemon.", severity="warning")

    def action_cancel_run(self) -> None:
        """Cancel the current run."""
        self.notify("Sending cancel signal...", severity="warning")
        # Similar to pause, needs IPC or DB signal.
