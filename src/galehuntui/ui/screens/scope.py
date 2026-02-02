from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header, 
    Footer, 
    Button, 
    Input, 
    Label, 
    TextArea, 
    ListView, 
    ListItem, 
    Static
)
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.binding import Binding
from typing import List, Dict, Any

class ScopeEditorScreen(Screen):
    """Screen for editing scope configurations."""
    
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("ctrl+s", "save_scope", "Save"),
        Binding("v", "validate_scope", "Validate"),
        Binding("n", "new_scope", "New"),
    ]

    CSS = """
    .scope-container {
        height: 100%;
        layout: horizontal;
    }
    
    .scope-sidebar {
        width: 30%;
        height: 100%;
        border-right: solid $border;
        background: $surface-light;
        padding: 1;
    }
    
    .scope-content {
        width: 1fr;
        height: 100%;
        padding: 1 2;
    }

    .form-group {
        height: auto;
        margin-bottom: 1;
    }
    
    .form-label {
        color: $text-muted;
        margin-bottom: 1;
    }

    TextArea {
        height: 8;
        border: solid $border;
        background: $surface-light;
    }
    
    TextArea:focus {
        border: solid $primary;
    }

    .sidebar-btn {
        width: 100%;
        margin-top: 1;
    }

    #scope-list {
        height: 1fr;
        border: solid $border;
        background: $surface;
        margin-bottom: 1;
    }

    .toolbar {
        height: auto;
        dock: bottom;
        padding-top: 1;
        align: right middle;
    }
    
    .toolbar Button {
        margin-left: 1;
    }
    """

    # Mock data for now
    current_scope = reactive(None)
    
    MOCK_SCOPES: Dict[str, Any] = {
        "example.com": {
            "target": "example.com",
            "allowlist": ["*.example.com", "api.example.com"],
            "denylist": ["admin.example.com", "*.staging.example.com"],
            "exclusions_paths": ["/logout", "/reset-password"],
            "exclusions_exts": [".pdf", ".doc", ".jpg"]
        },
        "test-app.local": {
            "target": "test-app.local",
            "allowlist": ["test-app.local"],
            "denylist": [],
            "exclusions_paths": [],
            "exclusions_exts": []
        }
    }

    def compose(self) -> ComposeResult:
        yield Header()
        
        with Container(classes="scope-container"):
            # Sidebar
            with Vertical(classes="scope-sidebar"):
                yield Label("Scope Files", classes="section-title")
                yield ListView(id="scope-list")
                yield Button("New Scope", variant="primary", classes="sidebar-btn", id="btn-new")
            
            # Main Content
            with VerticalScroll(classes="scope-content"):
                with Vertical(id="scope-form"):
                    with Vertical(classes="form-group"):
                        yield Label("Target Domain", classes="form-label")
                        yield Input(placeholder="example.com", id="input-target")
                    
                    with Vertical(classes="form-group"):
                        yield Label("Allowlist (one per line)", classes="form-label")
                        yield TextArea(id="input-allowlist")

                    with Vertical(classes="form-group"):
                        yield Label("Denylist (one per line)", classes="form-label")
                        yield TextArea(id="input-denylist")

                    with Horizontal(classes="form-group"):
                        with Vertical(classes="form-group-half", style="width: 1fr; margin-right: 1;"):
                            yield Label("Excluded Paths", classes="form-label")
                            yield TextArea(id="input-excl-paths")
                        
                        with Vertical(classes="form-group-half", style="width: 1fr;"):
                            yield Label("Excluded Exts", classes="form-label")
                            yield TextArea(id="input-excl-exts")

                    with Horizontal(classes="toolbar"):
                        yield Button("Validate", variant="default", id="btn-validate")
                        yield Button("Save Scope", variant="primary", id="btn-save")

        yield Footer()

    def on_mount(self) -> None:
        """Initialize the screen with data."""
        self.load_scopes()

    def load_scopes(self) -> None:
        """Load scopes into the list."""
        list_view = self.query_one("#scope-list", ListView)
        list_view.clear()
        
        for name in self.MOCK_SCOPES.keys():
            list_view.append(ListItem(Label(name), id=f"scope-{name}"))
        
        # Select first if available and nothing selected
        if self.MOCK_SCOPES and not self.current_scope:
            first = list(self.MOCK_SCOPES.keys())[0]
            self.load_scope_details(first)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle scope selection."""
        if event.item and event.item.id:
            name = event.item.id.replace("scope-", "")
            self.load_scope_details(name)

    def load_scope_details(self, name: str) -> None:
        """Populate form with scope data."""
        if name not in self.MOCK_SCOPES:
            return
            
        data = self.MOCK_SCOPES[name]
        self.current_scope = name
        
        self.query_one("#input-target", Input).value = data["target"]
        self.query_one("#input-allowlist", TextArea).text = "\n".join(data["allowlist"])
        self.query_one("#input-denylist", TextArea).text = "\n".join(data["denylist"])
        self.query_one("#input-excl-paths", TextArea).text = "\n".join(data["exclusions_paths"])
        self.query_one("#input-excl-exts", TextArea).text = "\n".join(data["exclusions_exts"])

    def action_new_scope(self) -> None:
        """Clear form for new scope."""
        self.current_scope = None
        self.query_one("#input-target", Input).value = ""
        self.query_one("#input-allowlist", TextArea).text = ""
        self.query_one("#input-denylist", TextArea).text = ""
        self.query_one("#input-excl-paths", TextArea).text = ""
        self.query_one("#input-excl-exts", TextArea).text = ""
        self.query_one("#input-target", Input).focus()
        self.notify("New scope template created")

    def action_save_scope(self) -> None:
        """Mock save scope."""
        target = self.query_one("#input-target", Input).value
        if not target:
            self.notify("Target domain is required", severity="error")
            return

        # Collect data
        data = {
            "target": target,
            "allowlist": [x for x in self.query_one("#input-allowlist", TextArea).text.split("\n") if x.strip()],
            "denylist": [x for x in self.query_one("#input-denylist", TextArea).text.split("\n") if x.strip()],
            "exclusions_paths": [x for x in self.query_one("#input-excl-paths", TextArea).text.split("\n") if x.strip()],
            "exclusions_exts": [x for x in self.query_one("#input-excl-exts", TextArea).text.split("\n") if x.strip()],
        }

        # Update mock storage
        self.MOCK_SCOPES[target] = data
        self.current_scope = target
        
        # Refresh list
        self.load_scopes()
        self.notify(f"Scope '{target}' saved successfully")

    def action_validate_scope(self) -> None:
        """Mock validation."""
        target = self.query_one("#input-target", Input).value
        if not target:
            self.notify("No target to validate", severity="error")
            return
            
        # Mock checks
        if "." not in target:
            self.notify("Invalid domain format", severity="warning")
        else:
            self.notify("Scope configuration is valid", severity="information")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.action_save_scope()
        elif event.button.id == "btn-validate":
            self.action_validate_scope()
        elif event.button.id == "btn-new":
            self.action_new_scope()

# For backward compatibility if needed, though we should update app.py
ScopeScreen = ScopeEditorScreen
