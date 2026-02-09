from pathlib import Path
from uuid import uuid4
import logging

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
    RadioSet,
    RadioButton,
)
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding

from galehuntui.core.constants import EngagementMode
from galehuntui.core.config import load_profile_config, get_config_dir, get_data_dir
from galehuntui.core.exceptions import ConfigError
from galehuntui.storage.database import Database
from galehuntui.orchestrator.factory import create_pipeline_orchestrator
from galehuntui.ui.screens.run_detail import RunDetailScreen


logger = logging.getLogger(__name__)

class NewRunScreen(Screen):
    """Screen for configuring and starting a new scan run."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    CSS = """
    NewRunScreen {
        align: center middle;
    }

    #form-container {
        width: 110;
        height: auto;
        border: solid $border;
        padding: 1;
        background: $surface;
    }

    #form-head {
        height: auto;
        padding: 0 1 1 1;
        border-bottom: solid $border;
        margin-bottom: 1;
    }

    #form-title {
        color: $primary;
        text-style: bold;
    }

    #form-subtitle {
        color: $text-muted;
    }

    #form-grid {
        height: auto;
        layout: horizontal;
        margin-bottom: 1;
    }

    .form-column {
        width: 1fr;
        height: auto;
        padding: 0 1;
    }

    .group-title {
        color: $primary;
        text-style: bold;
        margin-bottom: 1;
    }

    .form-group {
        margin-bottom: 1;
    }

    .form-group Label {
        color: $text-muted;
        margin-bottom: 1;
    }

    RadioSet {
        border: solid $border;
        padding: 1;
        background: $background;
    }

    RadioButton {
        width: 100%;
    }

    #btn-container {
        margin-top: 1;
        padding-top: 1;
        border-top: solid $border;
        align: right middle;
        height: auto;
    }

    Button {
        margin-left: 1;
    }

    .run-hint {
        color: $text-muted;
        margin-top: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="form-container"):
            with Vertical(id="form-head"):
                yield Label("Launch New Scan", id="form-title")
                yield Label("Configure target, profile, and operational constraints before execution.", id="form-subtitle")

            with Horizontal(id="form-grid"):
                with Vertical(classes="form-column"):
                    yield Label("Target & Profile", classes="group-title")

                    with Vertical(classes="form-group"):
                        yield Label("Target Domain / URL")
                        yield Input(placeholder="e.g., example.com", id="input-target")

                    with Vertical(classes="form-group"):
                        yield Label("Scan Profile")
                        yield Select([], prompt="Select Profile", id="select-profile")

                    with Vertical(classes="form-group"):
                        yield Label("Scope Configuration")
                        yield Select([], prompt="Select Scope File", id="select-scope")

                with Vertical(classes="form-column"):
                    yield Label("Execution Mode", classes="group-title")

                    with Vertical(classes="form-group"):
                        yield Label("Engagement Mode")
                        with RadioSet(id="radio-mode"):
                            for mode in EngagementMode:
                                label = mode.value.title().replace("_", " ")
                                yield RadioButton(label, id=f"mode-{mode.value}")

                    yield Label("Tip: Authorized mode is safest for repeatable testing. Esc returns to the dashboard.", classes="run-hint")

            with Collapsible(title="Advanced Options"):
                yield Checkbox("Generate HTML Report", value=True, id="chk-html")
                yield Checkbox("Export JSON", value=True, id="chk-json")
                yield Checkbox("Save Artifacts", value=True, id="chk-artifacts")
                yield Checkbox("Notify on Completion", value=False, id="chk-notify")
            
            with Horizontal(id="btn-container"):
                yield Button("Cancel", variant="error", id="btn-cancel")
                yield Button("Start Scan", variant="primary", id="btn-start")
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

        # Generate Run ID
        run_id = f"run-{uuid4().hex[:12]}"
        
        # Notify user
        self.notify(f"Starting run {run_id} for {target}...", severity="information")
        
        # Start background execution
        _worker = self._execute_run(run_id, target, profile, mode_value, scope_file)
        
        run_detail_screen = RunDetailScreen(run_id=run_id)
        
        # Close this screen and push run detail
        # We use call_after_refresh to ensure smooth transition
        def navigate():
            self.app.pop_screen()
            self.app.push_screen(run_detail_screen)
            
        self.call_after_refresh(navigate)

    @work(exclusive=True)
    async def _execute_run(self, run_id: str, target: str, profile_name: str, mode_value: str, scope_file: str) -> None:
        """Execute the pipeline in the background."""
        try:
            data_dir = get_data_dir()
            db_path = data_dir / "galehuntui.db"

            with Database(db_path) as db:
                db.init_db()

                engagement_mode = EngagementMode(mode_value)

                orchestrator = create_pipeline_orchestrator(
                    target=target,
                    profile_name=profile_name,
                    engagement_mode=engagement_mode,
                    db=db,
                    scope_file=Path(scope_file),
                    run_id=run_id,
                    runs_base_dir=data_dir / "runs",
                    tools_dir=Path.cwd() / "tools",
                )

                register_controller = getattr(self.app, "register_run_controller", None)
                if callable(register_controller):
                    register_controller(run_id, orchestrator)

                _state = await orchestrator.run(target)

            self.app.notify(f"Run {run_id} completed successfully!", severity="information")

        except Exception as e:
            logger.exception(f"Run {run_id} execution failed: {e}")
            self.app.notify(f"Run {run_id} failed: {e}", severity="error")
        finally:
            unregister_controller = getattr(self.app, "unregister_run_controller", None)
            if callable(unregister_controller):
                unregister_controller(run_id)
