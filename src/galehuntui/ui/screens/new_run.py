from pathlib import Path
from typing import List, Tuple

from textual.screen import Screen
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import (
    Header,
    Footer,
    Label,
    Input,
    Select,
    Button,
    Checkbox,
    Collapsible,
    Static,
    RadioSet,
    RadioButton,
)
from textual import on
from textual.app import ComposeResult

from galehuntui.core.constants import EngagementMode
from galehuntui.core.config import load_profile_config, get_config_dir
from galehuntui.core.exceptions import ConfigError

class NewRunScreen(Screen):
    """Screen for configuring and starting a new scan run."""

    CSS = """
    NewRunScreen {
        align: center middle;
    }

    #form-container {
        width: 60;
        height: auto;
        border: solid $primary;
        padding: 1 2;
        background: $surface;
    }

    .form-group {
        margin-bottom: 1;
    }

    Label {
        margin-bottom: 1;
        color: $text-muted;
    }

    RadioSet {
        background: transparent;
        border: none;
        padding: 0;
    }

    RadioButton {
        width: 100%;
        background: transparent;
    }

    #btn-container {
        margin-top: 2;
        align: right middle;
        height: auto;
    }

    Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="form-container"):
            yield Label("New Scan Configuration", classes="bold text-primary", id="form-title")
            
            with Vertical(classes="form-group"):
                yield Label("Target Domain / URL")
                yield Input(placeholder="e.g., example.com", id="input-target")
            
            with Vertical(classes="form-group"):
                yield Label("Scan Profile")
                yield Select([], prompt="Select Profile", id="select-profile")
            
            with Vertical(classes="form-group"):
                yield Label("Engagement Mode")
                with RadioSet(id="radio-mode"):
                    for mode in EngagementMode:
                        label = mode.value.title().replace("_", " ")
                        # Default to Authorized (this needs to be handled via value property or post-mount)
                        yield RadioButton(label, id=f"mode-{mode.value}")

            with Vertical(classes="form-group"):
                yield Label("Scope Configuration")
                yield Select([], prompt="Select Scope File", id="select-scope")

            with Collapsible(title="Advanced Options"):
                yield Checkbox("Generate HTML Report", value=True, id="chk-html")
                yield Checkbox("Export JSON", value=True, id="chk-json")
                yield Checkbox("Save Artifacts", value=True, id="chk-artifacts")
                yield Checkbox("Notify on Completion", value=False, id="chk-notify")
            
            with Horizontal(id="btn-container"):
                yield Button("Cancel", variant="error", id="btn-cancel")
                yield Button("Start Run", variant="primary", id="btn-start")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize form data."""
        self._load_profiles()
        self._load_scopes()
        
        # Set default mode
        radio_set = self.query_one("#radio-mode", RadioSet)
        # Select Authorized by default if exists
        authorized_btn = self.query_one(f"#mode-{EngagementMode.AUTHORIZED.value}", RadioButton)
        if authorized_btn:
            authorized_btn.value = True

    def _load_profiles(self) -> None:
        """Load available scan profiles into Select widget."""
        try:
            profiles = load_profile_config()
            options = []
            if isinstance(profiles, dict):
                for name, profile in profiles.items():
                    label = f"{profile.name} - {profile.description}"
                    options.append((label, name))
            
            select = self.query_one("#select-profile", Select)
            select.set_options(options)
            if options:
                select.value = options[0][1]  # Select first by default
                
        except ConfigError as e:
            self.notify(f"Error loading profiles: {e}", severity="error")

    def _load_scopes(self) -> None:
        """Load scope files from config directory."""
        config_dir = get_config_dir()
        options = []
        
        if config_dir.exists():
            for file_path in config_dir.glob("*.yaml"):
                if "scope" in file_path.name:
                    options.append((file_path.name, str(file_path)))
        
        select = self.query_one("#select-scope", Select)
        if options:
            select.set_options(options)
            # Default to scope.example.yaml or first
            default_scope = "scope.example.yaml"
            for label, value in options:
                if label == default_scope:
                    select.value = value
                    break
            else:
                select.value = options[0][1]
        else:
            select.set_options([("No scope files found", "")])
            select.disabled = True

    @on(Button.Pressed, "#btn-cancel")
    def action_cancel(self) -> None:
        """Return to previous screen."""
        self.app.pop_screen()

    @on(Button.Pressed, "#btn-start")
    def action_start_run(self) -> None:
        """Validate inputs and start run."""
        target_input = self.query_one("#input-target", Input)
        profile_select = self.query_one("#select-profile", Select)
        mode_radio = self.query_one("#radio-mode", RadioSet)
        scope_select = self.query_one("#select-scope", Select)

        target = target_input.value.strip()
        profile = profile_select.value
        scope_file = scope_select.value
        
        # Get selected mode from RadioSet
        selected_button = mode_radio.pressed_button
        if selected_button:
            # Extract mode value from ID (mode-bugbounty -> bugbounty)
            mode_value = selected_button.id.replace("mode-", "")
        else:
            mode_value = None

        # Validation
        if not target:
            self.notify("Target domain is required.", severity="error")
            target_input.focus()
            return

        if not profile or profile == Select.BLANK:
            self.notify("Please select a scan profile.", severity="error")
            return

        if not mode_value:
            self.notify("Please select an engagement mode.", severity="error")
            return
            
        if not scope_file or scope_file == Select.BLANK:
            self.notify("Please select a scope configuration.", severity="error")
            return

        # TODO: Here we would trigger the actual run creation via Orchestrator
        # For now, just notify and simulate success
        
        self.notify(f"Starting run for {target}...", severity="information")
        self.app.pop_screen()
        
        # Simulate switching to run details
        # self.app.push_screen("run_detail", run_id="new-run-id")
