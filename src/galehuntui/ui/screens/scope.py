from pathlib import Path
from typing import Dict, Any, Optional
import yaml

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
)
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.binding import Binding

from galehuntui.core.config import get_config_dir

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
        border-right: solid #2e344d;
        background: #1a1c29;
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
        color: #64748b;
        margin-bottom: 1;
    }

    TextArea {
        height: 8;
        border: solid #2e344d;
        background: #1a1c29;
    }
    
    TextArea:focus {
        border: solid #00f2ea;
    }

    .sidebar-btn {
        width: 100%;
        margin-top: 1;
    }

    #scope-list {
        height: 1fr;
        border: solid #2e344d;
        background: #0f111a;
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

    # Tracks the full path of the currently edited file
    current_scope_path: reactive[Optional[Path]] = reactive(None)
    
    # Cache scope data: path -> parsed dict
    _scope_cache: Dict[Path, Dict[str, Any]] = {}

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

    def get_scope_files(self) -> list[Path]:
        """Find all scope YAML files in configuration directories."""
        scope_files = []
        
        # Check project configs dir
        config_dir = get_config_dir()
        if config_dir.exists():
            for p in config_dir.glob("*.yaml"):
                # Simple heuristic: if filename starts with scope or contains scope, 
                # or we just try to parse all yamls and check structure?
                # For now, let's load all .yaml files in configs/ that look like scopes
                # or just all .yaml files except known ones like profiles.yaml/modes.yaml
                if p.name in ["profiles.yaml", "modes.yaml", "registry.yaml"]:
                    continue
                scope_files.append(p)
                
        # Check user config dir (~/.config/galehuntui)
        user_config = Path.home() / ".config" / "galehuntui"
        if user_config.exists():
            for p in user_config.glob("*.yaml"):
                if p.name in ["profiles.yaml", "modes.yaml", "registry.yaml"]:
                    continue
                scope_files.append(p)
                
        return sorted(list(set(scope_files)))

    def load_scopes(self) -> None:
        """Load scope files into the list."""
        list_view = self.query_one("#scope-list", ListView)
        list_view.clear()
        
        self._scope_cache.clear()
        files = self.get_scope_files()
        
        first_valid = None

        for path in files:
            try:
                # Try to load to verify it's a scope file and get the target
                with open(path, "r") as f:
                    data = yaml.safe_load(f)
                
                if not data or "target" not in data or "domain" not in data["target"]:
                    continue
                    
                target = data["target"]["domain"]
                self._scope_cache[path] = data
                
                # Create list item with path as ID (sanitized)
                safe_id = f"scope-{path.name.replace('.', '_')}"
                list_view.append(ListItem(Label(target), id=safe_id))
                
                if not first_valid:
                    first_valid = path
                    
            except Exception:
                # Skip invalid files
                continue
        
        # Select first if available and nothing selected
        if first_valid and not self.current_scope_path:
            self.load_scope_details(first_valid)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle scope selection."""
        if not event.item:
            return
            
        # Find path from cache that matches the label or ID logic
        # Since we can't easily store full path in ID safely, we look up by target name 
        # or we just iterate our cache. 
        # Better: iterate cache and match the label
        selected_label = event.item.query_one(Label).renderable
        
        for path, data in self._scope_cache.items():
            if str(selected_label) == data["target"]["domain"]:
                self.load_scope_details(path)
                return

    def load_scope_details(self, path: Path) -> None:
        """Populate form with scope data from file."""
        if path not in self._scope_cache:
            return
            
        data = self._scope_cache[path]
        self.current_scope_path = path
        
        target_info = data.get("target", {})
        scope_info = data.get("scope", {})
        exclusions = scope_info.get("exclusions", {})
        
        self.query_one("#input-target", Input).value = target_info.get("domain", "")
        self.query_one("#input-allowlist", TextArea).text = "\n".join(scope_info.get("allowlist", []))
        self.query_one("#input-denylist", TextArea).text = "\n".join(scope_info.get("denylist", []))
        self.query_one("#input-excl-paths", TextArea).text = "\n".join(exclusions.get("paths", []))
        self.query_one("#input-excl-exts", TextArea).text = "\n".join(exclusions.get("extensions", []))

    def action_new_scope(self) -> None:
        """Clear form for new scope."""
        self.current_scope_path = None
        self.query_one("#scope-list", ListView).index = None
        
        self.query_one("#input-target", Input).value = ""
        self.query_one("#input-allowlist", TextArea).text = ""
        self.query_one("#input-denylist", TextArea).text = ""
        self.query_one("#input-excl-paths", TextArea).text = ""
        self.query_one("#input-excl-exts", TextArea).text = ""
        self.query_one("#input-target", Input).focus()
        self.notify("New scope template created")

    def action_save_scope(self) -> None:
        """Save scope to file."""
        target = self.query_one("#input-target", Input).value.strip()
        if not target:
            self.notify("Target domain is required", severity="error")
            return

        # Collect data
        data = {
            "target": {
                "domain": target
            },
            "scope": {
                "allowlist": [x.strip() for x in self.query_one("#input-allowlist", TextArea).text.split("\n") if x.strip()],
                "denylist": [x.strip() for x in self.query_one("#input-denylist", TextArea).text.split("\n") if x.strip()],
                "exclusions": {
                    "paths": [x.strip() for x in self.query_one("#input-excl-paths", TextArea).text.split("\n") if x.strip()],
                    "extensions": [x.strip() for x in self.query_one("#input-excl-exts", TextArea).text.split("\n") if x.strip()]
                }
            }
        }

        # Determine file path
        if self.current_scope_path:
            save_path = self.current_scope_path
        else:
            # Create new file name based on domain
            filename = f"scope_{target.replace('.', '_')}.yaml"
            save_path = get_config_dir() / filename
        
        try:
            # Ensure directory exists
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, "w") as f:
                yaml.dump(data, f, sort_keys=False, default_flow_style=False)
                
            self.notify(f"Scope saved to {save_path.name}")
            
            # Refresh list and select the saved item
            self.load_scopes()
            
            # Update selection to the file we just saved
            # (Requires re-finding the path in the cache/list)
            # For simplicity, we just set current_scope_path
            self.current_scope_path = save_path
            
        except Exception as e:
            self.notify(f"Error saving scope: {e}", severity="error")

    def action_validate_scope(self) -> None:
        """Validate current form data."""
        target = self.query_one("#input-target", Input).value
        if not target:
            self.notify("No target to validate", severity="error")
            return
            
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

# For backward compatibility if needed
ScopeScreen = ScopeEditorScreen
