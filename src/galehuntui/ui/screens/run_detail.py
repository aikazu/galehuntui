from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, Footer, Label, Button, DataTable, RichLog, ProgressBar, 
    TabbedContent, TabPane
)
from textual.containers import Container, Horizontal
from datetime import datetime
import random

class RunDetailScreen(Screen):
    """Screen for monitoring a running scan or viewing a completed one."""
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("p", "toggle_pause", "Pause/Resume"),
        ("c", "cancel_run", "Cancel Run"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(classes="run-detail-container"):
            # Top Info Panel
            with Horizontal(classes="run-info-bar"):
                yield Label("Run ID: #run-20240203-001", classes="info-label")
                yield Label("Target: example.com", classes="info-label")
                yield Label("Status: RUNNING", classes="status-badge running", id="run-status")
                yield Label("Duration: 00:05:23", classes="info-label", id="run-duration")

            # Pipeline Progress
            yield Label("Pipeline Progress", classes="section-title")
            yield ProgressBar(total=100, show_eta=True, classes="pipeline-progress", id="run-progress")

            # Main Content Area
            with TabbedContent():
                with TabPane("Live Logs", id="tab-logs"):
                    yield RichLog(highlight=True, markup=True, id="run-log")
                
                with TabPane("Findings", id="tab-findings"):
                    yield DataTable(id="findings-table")
                
                with TabPane("Steps", id="tab-steps"):
                     yield DataTable(id="steps-table")

            # Controls
            with Horizontal(classes="controls-bar"):
                yield Button("Pause Run", variant="warning", id="btn-pause")
                yield Button("Cancel Run", variant="error", id="btn-cancel")
                yield Button("Export Report", variant="primary", id="btn-export")
        
        yield Footer()

    def on_mount(self) -> None:
        """Initialize widgets and start polling."""
        # Setup Findings Table
        findings_table = self.query_one("#findings-table", DataTable)
        findings_table.add_columns("ID", "Severity", "Type", "Host", "Confidence")
        findings_table.cursor_type = "row"

        # Setup Steps Table
        steps_table = self.query_one("#steps-table", DataTable)
        steps_table.add_columns("Step", "Status", "Duration")
        steps_table.add_rows([
            ("Subdomain Enumeration", "COMPLETED", "45s"),
            ("DNS Resolution", "COMPLETED", "12s"),
            ("HTTP Probing", "RUNNING", "Running..."),
            ("Vulnerability Scanning", "PENDING", "--"),
            ("Reporting", "PENDING", "--"),
        ])
        
        # Initial Log
        log = self.query_one("#run-log", RichLog)
        log.write("[green]INFO[/] Run started at " + datetime.now().strftime("%H:%M:%S"))
        log.write("[blue]INFO[/] Target: example.com")
        log.write("[blue]INFO[/] Loaded profile: standard")

        # Start mocking updates
        self.set_interval(1.0, self.update_mock_data)

    def update_mock_data(self) -> None:
        """Simulate updates from the backend."""
        # Update progress
        progress = self.query_one("#run-progress", ProgressBar)
        if progress.progress < 100:
            change = random.uniform(0, 2)
            progress.advance(change)
        
        # Add log entry
        log = self.query_one("#run-log", RichLog)
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if random.random() < 0.3:
            msg_types = [
                ("[blue]INFO[/]", "Scanning host..."),
                ("[blue]INFO[/]", "Analyzing response..."),
                ("[yellow]WARN[/]", "Slow response from server"),
                ("[green]SUCCESS[/]", "Found open port 80"),
            ]
            tag, msg = random.choice(msg_types)
            log.write(f"{tag} [{timestamp}] {msg}")

        # Add finding occasionally
        if random.random() < 0.05:
            table = self.query_one("#findings-table", DataTable)
            severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
            sev = random.choice(severities)
            
            # Simple color mapping for severity
            color_map = {
                "CRITICAL": "red",
                "HIGH": "orange",
                "MEDIUM": "yellow",
                "LOW": "blue",
                "INFO": "white"
            }
            color = color_map.get(sev, "white")
            
            vuln_types = ["XSS Reflected", "SQL Injection", "Open Redirect", "Sensitive Data Exposure"]
            
            table.add_row(
                f"F-{random.randint(1000, 9999)}",
                f"[{color}]{sev}[/]",
                random.choice(vuln_types),
                "admin.example.com",
                "Firm"
            )
            
            # Notify user
            self.notify(f"New {sev} finding detected!")
            
        # Update duration (mock)
        # In a real app, this would be calculated from start time
        duration_label = self.query_one("#run-duration", Label)
        current_text = str(duration_label.renderable)
        # Parse and increment simple mock duration if needed, or just leave it static for now
        # For this task, static or simple random update is fine. 
        # Let's just update the label to show it's "live"
        # actually, parsing "Duration: 00:05:23" is a bit much for a mock. 
        # I'll just leave it or maybe update it with a timestamp
        pass

    def action_toggle_pause(self) -> None:
        """Pause or resume the run."""
        btn = self.query_one("#btn-pause", Button)
        status = self.query_one("#run-status", Label)
        
        if str(btn.label) == "Pause Run":
            btn.label = "Resume Run"
            btn.variant = "success"
            status.update("Status: PAUSED")
            status.remove_class("running")
            self.notify("Run paused")
            # In real app, would call backend pause
        else:
            btn.label = "Pause Run"
            btn.variant = "warning"
            status.update("Status: RUNNING")
            status.add_class("running")
            self.notify("Run resumed")

    def action_cancel_run(self) -> None:
        """Cancel the current run."""
        self.notify("Cancelling run...", severity="warning")
        # In real app, would call backend cancel
        self.app.pop_screen()
