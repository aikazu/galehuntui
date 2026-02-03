from pathlib import Path
from typing import List, Tuple
from uuid import uuid4
from datetime import datetime
import asyncio
import importlib

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
from textual import on, work
from textual.app import ComposeResult

from galehuntui.core.constants import EngagementMode
from galehuntui.core.config import load_profile_config, get_config_dir, load_scope_config
from galehuntui.core.models import RunMetadata, ScopeConfig, RunConfig, RunState
from galehuntui.core.exceptions import ConfigError
from galehuntui.storage.database import Database
from galehuntui.orchestrator.pipeline import PipelineOrchestrator
from galehuntui.ui.screens.run_detail import RunDetailScreen

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

        # Generate Run ID
        run_id = f"run-{uuid4().hex[:12]}"
        
        # Notify user
        self.notify(f"Starting run {run_id} for {target}...", severity="information")
        
        # Start background execution
        _worker = self._execute_run(run_id, target, profile, mode_value, scope_file)
        
        # Instantiate and push RunDetailScreen
        # We manually set the run_id on the screen instance so it can use it (if updated)
        run_detail_screen = RunDetailScreen()
        run_detail_screen.run_id = run_id  # Monkey-patch/set attribute for future use
        
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
            # 1. Setup paths
            data_dir = Path.home() / ".local" / "share" / "galehuntui"
            db_path = data_dir / "galehuntui.db"
            run_dir = data_dir / "runs" / run_id
            
            # Create directories
            for subdir in ["artifacts", "evidence", "reports"]:
                (run_dir / subdir).mkdir(parents=True, exist_ok=True)
            
            # 2. Initialize Database
            db = Database(db_path)
            db.init_db()
            
            # 3. Load Configurations
            scope_config = load_scope_config(scope_file)
            
            profiles = load_profile_config()
            if profile_name not in profiles:
                raise ValueError(f"Profile {profile_name} not found")
            scan_profile = profiles[profile_name]
            
            engagement_mode = EngagementMode(mode_value)
            
            # 4. Create RunMetadata
            now = datetime.now()
            run_metadata = RunMetadata(
                id=run_id,
                target=target,
                profile=profile_name,
                engagement_mode=engagement_mode,
                state=RunState.PENDING,
                created_at=now,
                started_at=now,
                updated_at=now,
                run_dir=run_dir,
                artifacts_dir=run_dir / "artifacts",
                evidence_dir=run_dir / "evidence",
                reports_dir=run_dir / "reports",
                scope_config=scope_config,
            )
            
            # Save initial state
            db.save_run(run_metadata)
            
            # 5. Initialize Adapters (Dynamically to match CLI pattern)
            tools_dir = Path.cwd() / "tools"
            
            adapters = {}
            adapter_modules = {
                "subfinder": "galehuntui.tools.adapters.subfinder",
                "dnsx": "galehuntui.tools.adapters.dnsx",
                "httpx": "galehuntui.tools.adapters.httpx",
                "katana": "galehuntui.tools.adapters.katana",
                "gau": "galehuntui.tools.adapters.gau",
                "nuclei": "galehuntui.tools.adapters.nuclei",
                "dalfox": "galehuntui.tools.adapters.dalfox",
                "ffuf": "galehuntui.tools.adapters.ffuf",
                "sqlmap": "galehuntui.tools.adapters.sqlmap",
            }
            
            # Load adapters for steps in profile
            for tool_name in scan_profile.steps:
                if tool_name in adapter_modules:
                    try:
                        mod = importlib.import_module(adapter_modules[tool_name])
                        adapter_class = getattr(mod, f"{tool_name.capitalize()}Adapter", None)
                        if adapter_class:
                            # Construct bin path
                            bin_path = tools_dir / "bin" / tool_name
                            adapters[tool_name] = adapter_class(bin_path)
                    except Exception as e:
                        # Continue with warning
                        self.app.notify(f"Warning: Failed to load {tool_name}: {e}", severity="warning")

            # 6. Initialize Orchestrator
            orchestrator = PipelineOrchestrator.create_standard_pipeline(
                adapters=adapters,
                target=target,
                profile=scan_profile,
                scope=scope_config,
                engagement_mode=engagement_mode,
            )
            orchestrator.db = db
            
            # 7. Run Pipeline
            _state = await orchestrator.run(target)
            
            self.app.notify(f"Run {run_id} completed successfully!", severity="information")
            
        except Exception as e:
            self.app.notify(f"Run {run_id} failed: {e}", severity="error")
