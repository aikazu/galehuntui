from pathlib import Path
from typing import Any

import yaml
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Checkbox,
    ContentSwitcher,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Select,
    Static,
)

# We use standard XDG config path for user settings
# ~/.config/galehuntui/config.yaml


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
                            yield Checkbox("Check for updates on startup", value=True, id="chk-updates")
                        
                        with Vertical(classes="setting-item"):
                            yield Checkbox("Send anonymous usage statistics", value=False, id="chk-stats")
                        
                        with Vertical(classes="setting-item"):
                            yield Label("Default Download Path", classes="setting-label")
                            yield Input(placeholder="/home/user/galehuntui/downloads", id="input-download-path")

                    # Appearance Settings
                    with VerticalScroll(id="appearance", classes="settings-container"):
                        yield Label("Appearance", classes="section-title")
                        
                        with Vertical(classes="setting-item"):
                            yield Label("Theme", classes="setting-label")
                            yield Select(
                                options=[("Dark", "Dark"), ("Light", "Light"), ("System", "System")],
                                value="Dark",
                                allow_blank=False,
                                id="select-theme"
                            )
                        
                        with Vertical(classes="setting-item"):
                            yield Checkbox("Compact Mode", value=False, id="chk-compact")
                        
                        with Vertical(classes="setting-item"):
                            yield Checkbox("Show Animations", value=True, id="chk-animations")

                    # Performance Settings
                    with VerticalScroll(id="performance", classes="settings-container"):
                        yield Label("Performance", classes="section-title")
                        
                        with Vertical(classes="setting-item"):
                            yield Label("Max Concurrency", classes="setting-label")
                            yield Input(value="10", type="integer", id="input-concurrency")
                            yield Label("Maximum number of concurrent tasks", classes="setting-description")

                        with Vertical(classes="setting-item"):
                            yield Label("Request Timeout (seconds)", classes="setting-label")
                            yield Input(value="30", type="integer", id="input-timeout")

                    # Logging Settings
                    with VerticalScroll(id="logging", classes="settings-container"):
                        yield Label("Logging", classes="section-title")
                        
                        with Vertical(classes="setting-item"):
                            yield Label("Log Level", classes="setting-label")
                            yield Select(
                                options=[("DEBUG", "DEBUG"), ("INFO", "INFO"), ("WARNING", "WARNING"), ("ERROR", "ERROR")],
                                value="INFO",
                                allow_blank=False,
                                id="select-log-level"
                            )
                            
                        with Vertical(classes="setting-item"):
                            yield Checkbox("Enable File Logging", value=True, id="chk-file-logging")
                            
                        with Vertical(classes="setting-item"):
                            yield Label("Log File Path", classes="setting-label")
                            yield Input(value="~/.local/share/galehuntui/logs/app.log", id="input-log-path")

                    # About
                    with VerticalScroll(id="about", classes="settings-container"):
                        yield Label("About GaleHunTUI", classes="section-title")
                        yield Static("\nGaleHunTUI v1.0.0\n\nAutomated Web Pentesting Framework\n\nLicense: MIT\n\nBuilt with Textual & Typer")

                # Save Bar
                with Horizontal(id="save-bar"):
                    yield Button("Cancel", variant="error", id="btn-cancel")
                    yield Button("Save Changes", variant="primary", id="btn-save")

        yield Footer()

    def on_mount(self) -> None:
        """Load settings on mount."""
        self.load_settings()

    def get_config_path(self) -> Path:
        """Get path to config file."""
        return Path.home() / ".config" / "galehuntui" / "config.yaml"

    def load_settings(self) -> None:
        """Load settings from config file."""
        config_path = self.get_config_path()
        if not config_path.exists():
            return

        try:
            with config_path.open("r") as f:
                config = yaml.safe_load(f)
                
            if not config:
                return

            # General
            general = config.get("general", {})
            self.query_one("#chk-updates", Checkbox).value = general.get("check_updates", True)
            self.query_one("#chk-stats", Checkbox).value = general.get("send_stats", False)
            self.query_one("#input-download-path", Input).value = general.get("download_path", "")

            # Appearance
            appearance = config.get("appearance", {})
            theme = appearance.get("theme", "Dark")
            if theme in ["Dark", "Light", "System"]:
                self.query_one("#select-theme", Select).value = theme
            
            self.query_one("#chk-compact", Checkbox).value = appearance.get("compact", False)
            self.query_one("#chk-animations", Checkbox).value = appearance.get("animations", True)

            # Performance
            performance = config.get("performance", {})
            self.query_one("#input-concurrency", Input).value = str(performance.get("max_concurrency", 10))
            self.query_one("#input-timeout", Input).value = str(performance.get("timeout", 30))

            # Logging
            logging = config.get("logging", {})
            level = logging.get("level", "INFO")
            if level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
                self.query_one("#select-log-level", Select).value = level
                
            self.query_one("#chk-file-logging", Checkbox).value = logging.get("file_logging", True)
            self.query_one("#input-log-path", Input).value = logging.get("file_path", "~/.local/share/galehuntui/logs/app.log")

        except Exception as e:
            self.notify(f"Failed to load settings: {e}", severity="error")

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
        """Save settings to config file."""
        config_path = self.get_config_path()
        
        # Collect values
        try:
            config = {
                "general": {
                    "check_updates": self.query_one("#chk-updates", Checkbox).value,
                    "send_stats": self.query_one("#chk-stats", Checkbox).value,
                    "download_path": self.query_one("#input-download-path", Input).value,
                },
                "appearance": {
                    "theme": self.query_one("#select-theme", Select).value,
                    "compact": self.query_one("#chk-compact", Checkbox).value,
                    "animations": self.query_one("#chk-animations", Checkbox).value,
                },
                "performance": {
                    "max_concurrency": int(self.query_one("#input-concurrency", Input).value or 10),
                    "timeout": int(self.query_one("#input-timeout", Input).value or 30),
                },
                "logging": {
                    "level": self.query_one("#select-log-level", Select).value,
                    "file_logging": self.query_one("#chk-file-logging", Checkbox).value,
                    "file_path": self.query_one("#input-log-path", Input).value,
                }
            }
            
            # Ensure config directory exists
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with config_path.open("w") as f:
                yaml.dump(config, f, default_flow_style=False)
                
            self.notify("Settings saved successfully!")
            
        except ValueError as e:
            self.notify(f"Invalid input: {e}", severity="error")
        except Exception as e:
            self.notify(f"Failed to save settings: {e}", severity="error")
    
    @on(Button.Pressed, "#btn-cancel")
    def action_cancel(self) -> None:
        """Cancel and go back."""
        self.app.pop_screen()
