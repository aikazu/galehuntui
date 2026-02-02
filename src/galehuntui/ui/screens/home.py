from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, DataTable, Static, Label, Digits
from textual.containers import Container, Horizontal, Vertical
from textual.binding import Binding

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
        background: $surface-light;
        border: solid $border;
        layout: horizontal;
        padding: 0 1;
        margin-bottom: 1;
    }

    .stat-card {
        width: 1fr;
        height: 100%;
        align: center middle;
        border-right: solid $surface;
    }
    
    .stat-card:last-of-type {
        border-right: none;
    }

    .stat-value {
        text-align: center;
        color: $secondary;
        text-style: bold;
        width: 100%;
        content-align: center middle;
    }

    .stat-label {
        text-align: center;
        color: $text-muted;
        width: 100%;
    }

    /* Recent Runs Table */
    #recent-runs-container {
        height: 100%;
        border: solid $border;
        background: $surface;
        row-span: 1;
    }
    
    DataTable {
        height: 100%;
        background: $surface;
        border: none;
    }
    
    DataTable > .datatable--header {
        background: $surface-light;
        color: $primary;
        text-style: bold;
    }

    /* Side Panel */
    #side-panel {
        height: 100%;
        layout: vertical;
        row-gutter: 1;
    }

    .panel-header {
        background: $surface-light;
        color: $primary;
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
        background: $surface-light;
        border: solid $border;
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
        color: $success;
        margin-right: 1;
    }
    
    .status-text {
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(id="home-container"):
            # Top Stats Row
            with Horizontal(id="stats-panel"):
                yield self._make_stat_card("Total Runs", "42")
                yield self._make_stat_card("Critical Findings", "12")
                yield self._make_stat_card("Tools Installed", "15/18")
                yield self._make_stat_card("Last Scan", "2h ago")

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
                    yield self._make_status_row("Database", "Connected")
                    yield self._make_status_row("Docker", "Available")
                    yield self._make_status_row("Network", "Online")

        yield Footer()

    def _make_stat_card(self, label: str, value: str) -> Vertical:
        """Create a stat card with value and label."""
        # Using Label for value instead of Digits for better layout control in this grid
        return Vertical(
            Label(value, classes="stat-value"),
            Label(label, classes="stat-label"),
            classes="stat-card"
        )

    def _make_status_row(self, label: str, status: str) -> Horizontal:
        """Create a status row with a dot and text."""
        return Horizontal(
            Label("●", classes="status-dot"),
            Label(f"{label}: {status}", classes="status-text"),
            classes="status-row"
        )

    def on_mount(self) -> None:
        """Initialize data when screen is mounted."""
        table = self.query_one("#recent_runs_table", DataTable)
        table.add_columns("ID", "Target", "Profile", "Status", "Findings", "Date")
        
        # Mock Data
        mock_data = [
            ("RUN-1042", "example.com", "Standard", "Completed", "3 High, 5 Med", "2024-02-03 14:30"),
            ("RUN-1041", "api.test.org", "Quick", "Completed", "0 Issues", "2024-02-03 12:15"),
            ("RUN-1040", "staging.dev", "Deep", "Failed", "-", "2024-02-02 09:45"),
            ("RUN-1039", "legacy-app", "Standard", "Completed", "1 Critical", "2024-02-01 16:20"),
            ("RUN-1038", "intranet", "Quick", "Completed", "2 Low", "2024-02-01 10:00"),
        ]
        
        for row in mock_data:
            table.add_row(*row)

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
