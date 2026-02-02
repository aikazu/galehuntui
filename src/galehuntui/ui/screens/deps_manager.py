import asyncio
from typing import Any

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label

# Mock Dependency Manager since real one is missing implementation
class DependencyManager:
    """Manages dependencies like wordlists and templates."""
    
    def __init__(self):
        # Mock data
        self.deps = {
            "nuclei-templates": {
                "name": "Nuclei Templates",
                "type": "templates",
                "version": "v9.8.0",
                "status": "installed",
                "description": "Community curated list of templates for the nuclei engine."
            },
            "seclists": {
                "name": "SecLists",
                "type": "wordlists",
                "version": "-",
                "status": "missing",
                "description": "SecLists is the security tester's companion."
            },
            "fuzz-db": {
                "name": "FuzzDB",
                "type": "wordlists",
                "version": "-",
                "status": "missing",
                "description": "Dictionary of attack patterns and primitives."
            },
            "assetnote-wordlists": {
                "name": "Assetnote Wordlists",
                "type": "wordlists",
                "version": "-",
                "status": "missing",
                "description": "Automated generated wordlists from Assetnote."
            }
        }

    async def get_dependencies(self) -> dict[str, Any]:
        """Get all dependencies."""
        await asyncio.sleep(0.1) # Simulate IO
        return self.deps

    async def install(self, dep_id: str):
        """Install a dependency."""
        await asyncio.sleep(2) # Simulate download
        if dep_id in self.deps:
            self.deps[dep_id]["status"] = "installed"
            self.deps[dep_id]["version"] = "latest"

    async def update(self, dep_id: str):
        """Update a dependency."""
        await asyncio.sleep(2) # Simulate update
        if dep_id in self.deps:
            self.deps[dep_id]["version"] = "v.new"

    async def verify(self, dep_id: str) -> bool:
        """Verify a dependency."""
        return self.deps.get(dep_id, {}).get("status") == "installed"


class DepsManagerScreen(Screen):
    """Screen for managing dependencies (Wordlists, Templates)."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("u", "update_dep", "Update"),
        ("i", "install_dep", "Install"),
        ("v", "verify_dep", "Verify"),
    ]

    def __init__(self, name: str | None = None, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(name, id, classes)
        self.manager = DependencyManager()
        self.selected_dep_id: str | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        
        with Container(classes="tools-container"):
            with Vertical(classes="tools-section"):
                yield Label("Nuclei Templates", classes="section-title")
                yield DataTable(id="templates_table", cursor_type="row")
            
            with Vertical(classes="tools-section"):
                yield Label("Wordlists", classes="section-title")
                yield DataTable(id="wordlists_table", cursor_type="row")
            
            with Horizontal(classes="controls-bar"):
                yield Button("Install Selected", variant="primary", id="btn_install")
                yield Button("Update Selected", variant="default", id="btn_update")
                yield Button("Verify Selected", variant="default", id="btn_verify")

        yield Footer()

    def on_mount(self) -> None:
        """Set up tables and load data."""
        self._setup_table("templates_table")
        self._setup_table("wordlists_table")
        _ = self.load_deps()

    def _setup_table(self, table_id: str) -> None:
        """Configure table columns."""
        table = self.query_one(f"#{table_id}", DataTable)
        table.add_column("Name", width=25)
        table.add_column("Status", width=15)
        table.add_column("Version", width=15)
        table.add_column("Description")
        table.zebra_stripes = True

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track selected dependency."""
        row_key = event.row_key.value
        if row_key:
            self.selected_dep_id = row_key

    @work(exclusive=True)
    async def load_deps(self) -> None:
        """Load dependencies and populate tables."""
        try:
            deps = await self.manager.get_dependencies()
            
            t_table = self.query_one("#templates_table", DataTable)
            w_table = self.query_one("#wordlists_table", DataTable)
            
            t_table.clear()
            w_table.clear()
            
            for dep_id, config in deps.items():
                name = config.get("name", dep_id)
                status_raw = config.get("status", "unknown")
                version = config.get("version", "-")
                desc = config.get("description", "")
                dtype = config.get("type", "wordlists")
                
                if status_raw == "installed":
                    status = Text("Installed", style="bold green")
                else:
                    status = Text("Missing", style="bold red")
                
                row = [
                    Text(name, style="bold"),
                    status,
                    version,
                    desc
                ]
                
                if dtype == "templates":
                    t_table.add_row(*row, key=dep_id)
                else:
                    w_table.add_row(*row, key=dep_id)
                    
        except Exception as e:
            self.notify(f"Failed to load dependencies: {e}", severity="error")

    @work
    async def action_install_dep(self) -> None:
        """Install the selected dependency."""
        if not self.selected_dep_id:
            self.notify("No dependency selected", severity="warning")
            return
            
        self.notify(f"Installing {self.selected_dep_id}...", severity="information")
        try:
            await self.manager.install(self.selected_dep_id)
            self.notify(f"Installed {self.selected_dep_id}", severity="information")
            _ = self.load_deps()
        except Exception as e:
            self.notify(f"Failed to install: {e}", severity="error")

    @work
    async def action_update_dep(self) -> None:
        """Update the selected dependency."""
        if not self.selected_dep_id:
            self.notify("No dependency selected", severity="warning")
            return
            
        self.notify(f"Updating {self.selected_dep_id}...", severity="information")
        try:
            await self.manager.update(self.selected_dep_id)
            self.notify(f"Updated {self.selected_dep_id}", severity="information")
            _ = self.load_deps()
        except Exception as e:
            self.notify(f"Failed to update: {e}", severity="error")

    @work
    async def action_verify_dep(self) -> None:
        """Verify the selected dependency."""
        if not self.selected_dep_id:
            self.notify("No dependency selected", severity="warning")
            return
            
        is_valid = await self.manager.verify(self.selected_dep_id)
        if is_valid:
            self.notify(f"{self.selected_dep_id} is valid", severity="information")
        else:
            self.notify(f"{self.selected_dep_id} is invalid or missing", severity="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button clicks."""
        if event.button.id == "btn_install":
            _ = self.action_install_dep()
        elif event.button.id == "btn_update":
            _ = self.action_update_dep()
        elif event.button.id == "btn_verify":
            _ = self.action_verify_dep()
