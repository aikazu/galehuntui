from dataclasses import replace
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    SelectionList,
    Static,
)

from galehuntui.core.config import load_profile_config, save_profiles_config
from galehuntui.core.exceptions import ConfigError
from galehuntui.core.models import ScanProfile


TOOL_OPTIONS: list[tuple[str, str]] = [
    ("Subfinder (Subdomain Enum)", "subfinder"),
    ("DNSx (DNS Resolution)", "dnsx"),
    ("HTTPx (HTTP Probing)", "httpx"),
    ("Katana (Crawling)", "katana"),
    ("GAU (URL Discovery)", "gau"),
    ("Nuclei (Vuln Scanning)", "nuclei"),
    ("Dalfox (XSS)", "dalfox"),
    ("FFuF (Fuzzing)", "ffuf"),
    ("SQLMap (SQL Injection)", "sqlmap"),
]


class ProfilesScreen(Screen):
    """Screen for managing scan profiles with YAML persistence."""

    CSS_PATH = "../styles/main.tcss"

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]

    current_profile_id: reactive[Optional[str]] = reactive(None)

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        super().__init__(name, id, classes)
        self._profiles: dict[str, ScanProfile] = {}

    def compose(self) -> ComposeResult:
        yield Header()

        with Container(classes="profiles-container"):
            with Vertical(classes="profiles-sidebar"):
                yield Label("Profiles", classes="section-title")
                yield ListView(id="profiles-list")
                yield Button("Create Profile", id="btn-new", variant="default", classes="sidebar-btn")

            with Vertical(classes="profiles-content"):
                yield Label("Profile Details", classes="section-title")

                with Vertical(classes="form-group"):
                    yield Label("Name")
                    yield Input(placeholder="Profile Name", id="input-name")

                with Vertical(classes="form-group"):
                    yield Label("Description")
                    yield Input(placeholder="Description", id="input-desc")

                with Horizontal(classes="form-row"):
                    with Vertical(classes="form-group-half"):
                        yield Label("Timeout (seconds)")
                        yield Input(placeholder="300", id="input-timeout", type="integer")
                    with Vertical(classes="form-group-half"):
                        yield Label("Rate Limit")
                        yield Input(placeholder="30/s", id="input-rate")

                yield Label("Pipeline Steps", classes="section-title mt-1")
                yield SelectionList[str](id="list-steps")

                with Horizontal(classes="controls-bar"):
                    yield Static("Esc Back", classes="shortcut-hint")
                    yield Button("Delete Profile", variant="error", id="btn-delete", classes="mr-1")
                    yield Button("Clone Profile", variant="default", id="btn-clone", classes="mr-1")
                    yield Button("Save Profile", variant="primary", id="btn-save")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize profile data and step options."""
        steps_list = self.query_one("#list-steps", SelectionList)
        for label, value in TOOL_OPTIONS:
            steps_list.add_option((label, value))

        self._load_profiles_from_disk()
        _ = self._refresh_list()

        if self._profiles:
            first_profile_id = sorted(self._profiles.keys())[0]
            self.query_one("#profiles-list", ListView).index = 0
            self._load_profile(first_profile_id)
        else:
            self.on_new_profile()

    def _load_profiles_from_disk(self) -> None:
        """Load profiles from profiles.yaml."""
        try:
            loaded = load_profile_config()
            if not isinstance(loaded, dict):
                raise ConfigError("Invalid profile configuration format")
            self._profiles = loaded
        except ConfigError as exc:
            self.notify(f"Failed to load profiles: {exc}", severity="error")
            self._profiles = {}

    @work(exclusive=True)
    async def _refresh_list(self) -> None:
        """Re-render the profiles list."""
        list_view = self.query_one("#profiles-list", ListView)
        await list_view.clear()

        for profile_id in sorted(self._profiles.keys()):
            profile = self._profiles[profile_id]
            item = ListItem(Label(f"{profile.name} [{profile_id}]"), id=f"profile-item-{profile_id}")
            list_view.append(item)

    def _load_profile(self, profile_id: str) -> None:
        """Load profile data into the form."""
        profile = self._profiles.get(profile_id)
        if profile is None:
            return

        self.current_profile_id = profile_id

        self.query_one("#input-name", Input).value = profile.name
        self.query_one("#input-desc", Input).value = profile.description
        self.query_one("#input-timeout", Input).value = str(profile.timeout)
        self.query_one("#input-rate", Input).value = profile.rate_limit

        steps_list = self.query_one("#list-steps", SelectionList)
        steps_list.deselect_all()
        for step in profile.steps:
            try:
                steps_list.select(step)
            except (ValueError, KeyError):
                continue

    def _normalize_profile_id(self, raw_name: str) -> str:
        """Create filesystem-safe profile id from profile name."""
        normalized = "".join(
            char.lower() if char.isalnum() else "_"
            for char in raw_name.strip()
        )
        normalized = "_".join(part for part in normalized.split("_") if part)
        if normalized:
            return normalized
        return f"profile_{len(self._profiles) + 1}"

    def _next_available_profile_id(self, base_id: str) -> str:
        """Generate a unique profile id based on a preferred base id."""
        if base_id not in self._profiles:
            return base_id

        index = 2
        while f"{base_id}_{index}" in self._profiles:
            index += 1
        return f"{base_id}_{index}"

    def _collect_form_profile(self) -> tuple[str, ScanProfile]:
        """Collect and validate profile data from form widgets."""
        name = self.query_one("#input-name", Input).value.strip()
        description = self.query_one("#input-desc", Input).value.strip()
        timeout_value = self.query_one("#input-timeout", Input).value.strip()
        rate_limit = self.query_one("#input-rate", Input).value.strip() or "30/s"
        selected_steps = list(self.query_one("#list-steps", SelectionList).selected)

        if not name:
            raise ValueError("Profile name is required")

        if not selected_steps:
            raise ValueError("Select at least one pipeline step")

        timeout = int(timeout_value or "0")
        if timeout <= 0:
            raise ValueError("Timeout must be a positive integer")

        profile_id = self.current_profile_id
        if profile_id is None:
            profile_id = self._next_available_profile_id(
                self._normalize_profile_id(name)
            )

        existing = self._profiles.get(profile_id)
        concurrency = existing.concurrency if existing else 10
        use_cases = existing.use_cases if existing else []

        profile = ScanProfile(
            name=name,
            description=description,
            steps=selected_steps,
            concurrency=concurrency,
            rate_limit=rate_limit,
            timeout=timeout,
            use_cases=use_cases,
        )

        return profile_id, profile

    @on(ListView.Selected, "#profiles-list")
    def on_profile_selected(self, event: ListView.Selected) -> None:
        """Handle profile selection from list."""
        if event.item and event.item.id:
            profile_id = event.item.id.replace("profile-item-", "")
            self._load_profile(profile_id)

    @on(Button.Pressed, "#btn-new")
    def on_new_profile(self) -> None:
        """Clear form for creating a new profile."""
        self.current_profile_id = None
        self.query_one("#profiles-list", ListView).index = None

        self.query_one("#input-name", Input).value = ""
        self.query_one("#input-desc", Input).value = ""
        self.query_one("#input-timeout", Input).value = "300"
        self.query_one("#input-rate", Input).value = "30/s"
        self.query_one("#list-steps", SelectionList).deselect_all()
        self.query_one("#input-name", Input).focus()

    @on(Button.Pressed, "#btn-save")
    def on_save(self) -> None:
        """Save the current profile to profiles.yaml."""
        try:
            profile_id, profile = self._collect_form_profile()
            self._profiles[profile_id] = profile
            save_profiles_config(self._profiles)

            self.current_profile_id = profile_id
            _ = self._refresh_list()

            profile_ids = sorted(self._profiles.keys())
            selected_index = profile_ids.index(profile_id)
            self.query_one("#profiles-list", ListView).index = selected_index

            self.notify(f"Profile '{profile.name}' saved")
        except ValueError as exc:
            self.notify(str(exc), severity="error")
        except ConfigError as exc:
            self.notify(f"Failed to persist profile: {exc}", severity="error")

    @on(Button.Pressed, "#btn-clone")
    def on_clone(self) -> None:
        """Clone the currently selected profile."""
        if self.current_profile_id is None:
            self.notify("Select a profile to clone", severity="warning")
            return

        current_profile = self._profiles.get(self.current_profile_id)
        if current_profile is None:
            self.notify("Selected profile not found", severity="error")
            return

        clone_base_id = f"{self.current_profile_id}_copy"
        clone_id = self._next_available_profile_id(clone_base_id)
        cloned_profile = replace(current_profile, name=f"{current_profile.name} (Copy)")

        try:
            self._profiles[clone_id] = cloned_profile
            save_profiles_config(self._profiles)
            _ = self._refresh_list()

            profile_ids = sorted(self._profiles.keys())
            selected_index = profile_ids.index(clone_id)
            self.query_one("#profiles-list", ListView).index = selected_index
            self._load_profile(clone_id)

            self.notify(f"Cloned profile as '{clone_id}'")
        except ConfigError as exc:
            self.notify(f"Failed to persist cloned profile: {exc}", severity="error")

    @on(Button.Pressed, "#btn-delete")
    def on_delete(self) -> None:
        """Delete the currently selected profile."""
        if self.current_profile_id is None:
            self.notify("Select a profile to delete", severity="warning")
            return

        deleted_profile_id = self.current_profile_id
        profile_name = self._profiles[deleted_profile_id].name

        del self._profiles[deleted_profile_id]

        try:
            save_profiles_config(self._profiles)
            _ = self._refresh_list()
            self.notify(f"Deleted profile '{profile_name}'")
        except ConfigError as exc:
            self.notify(f"Failed to persist profile deletion: {exc}", severity="error")
            return

        remaining_ids = sorted(self._profiles.keys())
        if not remaining_ids:
            self.on_new_profile()
            return

        self.query_one("#profiles-list", ListView).index = 0
        self._load_profile(remaining_ids[0])
