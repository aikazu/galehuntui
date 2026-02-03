from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Container
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    Button,
    Input,
    Label,
    ListView,
    ListItem,
    SelectionList,
    Static,
)
from textual.reactive import reactive
from textual.message import Message

from dataclasses import dataclass, field
from typing import List, Optional
import copy

# --- Mock Models & Persistence ---

@dataclass
class Profile:
    id: str
    name: str
    description: str
    timeout: int
    rate_limit: str  # e.g. "50/s"
    steps: List[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return f"{self.name}"

class ProfileManager:
    """Mock persistence for profiles."""
    
    def __init__(self):
        self._profiles: List[Profile] = [
            Profile(
                id="quick",
                name="Quick Scan",
                description="Fast reconnaissance only",
                timeout=300,
                rate_limit="50/s",
                steps=["subfinder", "dnsx", "httpx"]
            ),
            Profile(
                id="standard",
                name="Standard Scan",
                description="Balanced recon + vuln scan",
                timeout=1800,
                rate_limit="30/s",
                steps=["subfinder", "dnsx", "httpx", "katana", "gau", "nuclei"]
            ),
            Profile(
                id="deep",
                name="Deep Scan",
                description="Full pipeline with injection testing",
                timeout=7200,
                rate_limit="10/s",
                steps=["subfinder", "dnsx", "httpx", "katana", "gau", "nuclei", "dalfox", "ffuf", "sqlmap"]
            ),
        ]
        self._available_tools = [
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

    def get_all(self) -> List[Profile]:
        return self._profiles

    def get(self, profile_id: str) -> Optional[Profile]:
        for p in self._profiles:
            if p.id == profile_id:
                return p
        return None

    def save(self, profile: Profile) -> None:
        existing = self.get(profile.id)
        if existing:
            index = self._profiles.index(existing)
            self._profiles[index] = profile
        else:
            self._profiles.append(profile)

    def delete(self, profile_id: str) -> None:
        self._profiles = [p for p in self._profiles if p.id != profile_id]
        
    def get_tools(self):
        return self._available_tools

# --- UI Screen ---

class ProfilesScreen(Screen):
    """Screen for managing scan profiles."""
    
    CSS_PATH = "../styles/main.tcss" # Reusing main styles + local if needed
    
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
    ]
    
    # Reactive state to track currently selected profile ID
    current_profile_id: reactive[Optional[str]] = reactive(None)

    def __init__(self, name: str | None = None, id: str | None = None, classes: str | None = None):
        super().__init__(name, id, classes)
        self.manager = ProfileManager()
        self.is_dirty = False

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(classes="profiles-container"):
            # Sidebar
            with Vertical(classes="profiles-sidebar"):
                yield Label("Profiles", classes="section-title")
                yield ListView(id="profiles-list")
                yield Button("New Profile", id="btn-new", variant="default", classes="sidebar-btn")
            
            # Main Content
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
                        yield Label("Timeout (sec)")
                        yield Input(placeholder="300", id="input-timeout", type="integer")
                    with Vertical(classes="form-group-half"):
                        yield Label("Rate Limit")
                        yield Input(placeholder="30/s", id="input-rate")

                yield Label("Pipeline Steps (Tools)", classes="section-title mt-1")
                yield SelectionList[str](id="list-steps")
                
                with Horizontal(classes="controls-bar"):
                    yield Button("Delete", variant="error", id="btn-delete", classes="mr-1")
                    yield Button("Clone", variant="default", id="btn-clone", classes="mr-1")
                    yield Button("Save", variant="primary", id="btn-save")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the screen data."""
        self._refresh_list()
        
        # Populate tools selection list (static for now)
        steps_list = self.query_one("#list-steps", SelectionList)
        for label, value in self.manager.get_tools():
            steps_list.add_option((label, value))
            
        # Select first profile if exists
        profiles = self.manager.get_all()
        if profiles:
            self.query_one("#profiles-list", ListView).index = 0
            self._load_profile(profiles[0].id)

    def _refresh_list(self) -> None:
        """Re-render the profiles list."""
        list_view = self.query_one("#profiles-list", ListView)
        list_view.clear()
        
        # Schedule repopulation after clear completes to avoid DuplicateIds
        def populate() -> None:
            for profile in self.manager.get_all():
                item = ListItem(Label(profile.name), id=f"profile-item-{profile.id}")
                list_view.append(item)
        
        self.call_after_refresh(populate)

    def _load_profile(self, profile_id: str) -> None:
        """Load profile data into the form."""
        profile = self.manager.get(profile_id)
        if not profile:
            return

        self.current_profile_id = profile_id
        
        self.query_one("#input-name", Input).value = profile.name
        self.query_one("#input-desc", Input).value = profile.description
        self.query_one("#input-timeout", Input).value = str(profile.timeout)
        self.query_one("#input-rate", Input).value = profile.rate_limit
        
        steps_list = self.query_one("#list-steps", SelectionList)
        # Reset selection first
        steps_list.deselect_all()
        
        # Select steps for this profile
        for step in profile.steps:
            # We need to find the option index or use select functionality
            # SelectionList doesn't accept values directly easily in all versions, 
            # but select() works with values if they exist.
            try:
                steps_list.select(step)
            except (ValueError, KeyError):
                # Step may not exist in selection list - skip invalid steps
                continue

    def _get_form_data(self) -> Profile:
        """Collect data from form widgets."""
        steps_list = self.query_one("#list-steps", SelectionList)
        
        # Generate a new ID if creating new, or use current
        pid = self.current_profile_id if self.current_profile_id else f"profile_{len(self.manager.get_all()) + 1}"
        
        return Profile(
            id=pid,
            name=self.query_one("#input-name", Input).value,
            description=self.query_one("#input-desc", Input).value,
            timeout=int(self.query_one("#input-timeout", Input).value or "0"),
            rate_limit=self.query_one("#input-rate", Input).value,
            steps=steps_list.selected
        )

    @on(ListView.Selected, "#profiles-list")
    def on_profile_selected(self, event: ListView.Selected) -> None:
        """Handle list selection."""
        # Extract profile ID from ListItem ID "profile-item-{id}"
        if event.item and event.item.id:
            profile_id = event.item.id.replace("profile-item-", "")
            self._load_profile(profile_id)

    @on(Button.Pressed, "#btn-new")
    def on_new_profile(self) -> None:
        """Clear form for new profile."""
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
        """Save the current profile."""
        try:
            profile = self._get_form_data()
            if not profile.name:
                self.notify("Profile name is required", severity="error")
                return
                
            is_new = self.manager.get(profile.id) is None
            
            self.manager.save(profile)
            self.notify(f"Profile '{profile.name}' saved!")
            
            # Refresh list and re-select
            self._refresh_list()
            
            # Find the item index to select it
            profiles = self.manager.get_all()
            for idx, p in enumerate(profiles):
                if p.id == profile.id:
                    self.query_one("#profiles-list", ListView).index = idx
                    break
            
            self.current_profile_id = profile.id
            
        except ValueError:
            self.notify("Invalid input format", severity="error")

    @on(Button.Pressed, "#btn-clone")
    def on_clone(self) -> None:
        """Clone the currently selected profile."""
        if not self.current_profile_id:
            return
            
        current = self.manager.get(self.current_profile_id)
        if current:
            new_profile = copy.deepcopy(current)
            new_profile.id = f"{current.id}_copy_{len(self.manager.get_all())}"
            new_profile.name = f"{current.name} (Copy)"
            self.manager.save(new_profile)
            
            self._refresh_list()
            self.notify(f"Cloned to '{new_profile.name}'")

    @on(Button.Pressed, "#btn-delete")
    def on_delete(self) -> None:
        """Delete the currently selected profile."""
        if not self.current_profile_id:
            return
            
        self.manager.delete(self.current_profile_id)
        self.notify("Profile deleted")
        self._refresh_list()
        
        # Reset form or select first available
        profiles = self.manager.get_all()
        if profiles:
            self.query_one("#profiles-list", ListView).index = 0
            self._load_profile(profiles[0].id)
        else:
            self.on_new_profile()
