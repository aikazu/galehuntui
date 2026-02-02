from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Label, ListView, ListItem, ContentSwitcher, Button, 
    Input, Checkbox, Select, Static, Header, Footer
)
from textual import on
from textual.binding import Binding

class SettingsScreen(Screen):
    """Settings configuration screen."""

    CSS = """
    SettingsScreen {
        layout: horizontal;
        background: $surface;
    }

    #sidebar {
        width: 30;
        height: 100%;
        dock: left;
        background: $surface-light;
        border-right: solid $border;
    }

    #sidebar-title {
        padding: 1 2;
        background: $surface-lighter;
        width: 100%;
        text-style: bold;
        color: $primary;
    }

    #sidebar-list {
        padding: 1;
    }

    ListItem {
        padding: 1 2;
        margin-bottom: 1;
        background: $surface-light;
        color: $text;
    }

    ListItem:hover {
        background: $surface-lighter;
    }

    ListItem.-selected {
        background: $surface-lighter;
        color: $primary;
        border-left: wide $primary;
    }

    #content {
        height: 100%;
        width: 1fr;
        padding: 0;
    }

    .settings-container {
        padding: 1 2;
        height: 1fr;
    }

    .settings-group {
        height: auto;
    }

    .setting-item {
        margin-bottom: 2;
        height: auto;
    }

    .setting-label {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }
    
    .setting-description {
        color: $text-muted;
        margin-bottom: 1;
        text-style: italic;
    }

    #save-bar {
        dock: bottom;
        height: 5;
        align: right middle;
        padding-right: 2;
        padding-top: 1;
        padding-bottom: 1;
        border-top: solid $border;
        background: $surface-light;
    }

    #btn-cancel {
        margin-right: 2;
    }
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+s", "save_settings", "Save"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal():
            # Sidebar
            with Vertical(id="sidebar"):
                yield Label("Categories", id="sidebar-title")
                yield ListView(
                    ListItem(Label("General"), id="nav-general"),
                    ListItem(Label("Appearance"), id="nav-appearance"),
                    ListItem(Label("Performance"), id="nav-performance"),
                    ListItem(Label("Logging"), id="nav-logging"),
                    ListItem(Label("About"), id="nav-about"),
                    id="sidebar-list",
                    initial_index=0
                )

            # Content Area
            with Vertical(id="content"):
                with ContentSwitcher(initial="general"):
                    # General Settings
                    with VerticalScroll(id="general", classes="settings-container"):
                        yield Label("General Settings", classes="section-title")
                        
                        with Vertical(classes="setting-item"):
                            yield Checkbox("Check for updates on startup", value=True)
                        
                        with Vertical(classes="setting-item"):
                            yield Checkbox("Send anonymous usage statistics", value=False)
                        
                        with Vertical(classes="setting-item"):
                            yield Label("Default Download Path", classes="setting-label")
                            yield Input(placeholder="/home/user/galehuntui/downloads")

                    # Appearance Settings
                    with VerticalScroll(id="appearance", classes="settings-container"):
                        yield Label("Appearance", classes="section-title")
                        
                        with Vertical(classes="setting-item"):
                            yield Label("Theme", classes="setting-label")
                            yield Select(
                                options=[("Dark", "Dark"), ("Light", "Light"), ("System", "System")],
                                value="Dark",
                                allow_blank=False
                            )
                        
                        with Vertical(classes="setting-item"):
                            yield Checkbox("Compact Mode", value=False)
                        
                        with Vertical(classes="setting-item"):
                            yield Checkbox("Show Animations", value=True)

                    # Performance Settings
                    with VerticalScroll(id="performance", classes="settings-container"):
                        yield Label("Performance", classes="section-title")
                        
                        with Vertical(classes="setting-item"):
                            yield Label("Max Concurrency", classes="setting-label")
                            yield Input(value="10", type="integer")
                            yield Label("Maximum number of concurrent tasks", classes="setting-description")

                        with Vertical(classes="setting-item"):
                            yield Label("Request Timeout (seconds)", classes="setting-label")
                            yield Input(value="30", type="integer")

                    # Logging Settings
                    with VerticalScroll(id="logging", classes="settings-container"):
                        yield Label("Logging", classes="section-title")
                        
                        with Vertical(classes="setting-item"):
                            yield Label("Log Level", classes="setting-label")
                            yield Select(
                                options=[("DEBUG", "DEBUG"), ("INFO", "INFO"), ("WARNING", "WARNING"), ("ERROR", "ERROR")],
                                value="INFO",
                                allow_blank=False
                            )
                            
                        with Vertical(classes="setting-item"):
                            yield Checkbox("Enable File Logging", value=True)
                            
                        with Vertical(classes="setting-item"):
                            yield Label("Log File Path", classes="setting-label")
                            yield Input(value="~/.local/share/galehuntui/logs/app.log")

                    # About
                    with VerticalScroll(id="about", classes="settings-container"):
                        yield Label("About GaleHunTUI", classes="section-title")
                        yield Static("\nGaleHunTUI v1.0.0\n\nAutomated Web Pentesting Framework\n\nLicense: MIT\n\nBuilt with Textual & Typer")

                # Save Bar
                with Horizontal(id="save-bar"):
                    yield Button("Cancel", variant="error", id="btn-cancel")
                    yield Button("Save Changes", variant="primary", id="btn-save")

        yield Footer()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle sidebar selection."""
        switcher = self.query_one(ContentSwitcher)
        
        # Map list item ID to content ID
        item_id = event.item.id
        if item_id:
            content_id = item_id.replace("nav-", "")
            if content_id in ["general", "appearance", "performance", "logging", "about"]:
                switcher.current = content_id

    @on(Button.Pressed, "#btn-save")
    def action_save_settings(self) -> None:
        """Mock save settings."""
        self.notify("Settings saved successfully!")
        # In a real app, we would write to config here
    
    @on(Button.Pressed, "#btn-cancel")
    def action_cancel(self) -> None:
        """Cancel and go back."""
        self.app.pop_screen()
