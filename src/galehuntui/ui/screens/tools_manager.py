from pathlib import Path
from typing import Any

from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static

from galehuntui.tools.installer import ToolInstaller
from galehuntui.core.exceptions import ToolInstallError


class ToolsManagerScreen(Screen):
    """Screen for managing external tools."""

    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("u", "update_tool", "Update"),
        ("i", "install_tool", "Install"),
        ("a", "install_all", "Install All"),
        ("v", "verify_tool", "Verify"),
    ]

    def __init__(self, name: str | None = None, id: str | None = None, classes: str | None = None) -> None:
        super().__init__(name, id, classes)
        # Initialize installer with default tools directory
        self.tools_dir = Path("tools").absolute()
        self.installer = ToolInstaller(self.tools_dir)
        self.registry: dict[str, Any] = {}
        self.selected_tool_id: str | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        
        with Container(classes="tools-container"):
            with Vertical(classes="tools-section"):
                yield Label("Core Tools (Required)", classes="section-title")
                yield DataTable(id="core_tools_table", cursor_type="row")
            
            with Vertical(classes="tools-section"):
                yield Label("Optional Tools", classes="section-title")
                yield DataTable(id="optional_tools_table", cursor_type="row")
            
            with Horizontal(classes="controls-bar"):
                yield Button("Install Selected", variant="primary", id="btn_install")
                yield Button("Update Selected", variant="default", id="btn_update")
                yield Button("Verify Selected", variant="default", id="btn_verify")
                yield Button("Install All Missing", variant="success", id="btn_install_all")

        yield Footer()

    def on_mount(self) -> None:
        """Set up tables and load data."""
        self._setup_table("core_tools_table")
        self._setup_table("optional_tools_table")
        # Start loading tools in background
        _ = self.load_tools()

    def _setup_table(self, table_id: str) -> None:
        """Configure table columns."""
        table = self.query_one(f"#{table_id}", DataTable)
        table.add_column("Tool", width=15)
        table.add_column("Status", width=15)
        table.add_column("Version", width=15)
        table.add_column("Description")
        table.zebra_stripes = True

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Track selected tool when row is highlighted."""
        row_key = event.row_key.value
        if row_key:
            self.selected_tool_id = row_key
            
            # Clear cursor in the other table to avoid confusion is tricky,
            # so we just track the last highlighted one.

    @work(exclusive=True)
    async def load_tools(self) -> None:
        """Load tools from registry and update status."""
        try:
            self.registry = self.installer.load_registry()
            tools = self.registry.get("tools", {})
            
            core_table = self.query_one("#core_tools_table", DataTable)
            opt_table = self.query_one("#optional_tools_table", DataTable)
            
            core_table.clear()
            opt_table.clear()
            
            # Sort tools by name
            sorted_tools = sorted(tools.items())
            
            for tool_id, config in sorted_tools:
                await self._add_tool_row(tool_id, config)
                
        except Exception as e:
            self.notify(f"Failed to load tools: {e}", severity="error")

    async def _add_tool_row(self, tool_id: str, config: dict[str, Any]) -> None:
        """Add a row to the appropriate table."""
        name = config.get("name", tool_id)
        description = config.get("description", "")
        required = config.get("required", False)
        
        # Determine status
        is_installed = self.installer.verify_tool(tool_id)
        version = await self.installer.get_tool_version(tool_id) if is_installed else "-"
        
        status = Text("Installed", style="bold green") if is_installed else Text("Missing", style="bold red")
        
        row = [
            Text(name, style="bold"),
            status,
            version or "Unknown",
            description
        ]
        
        table_id = "#core_tools_table" if required else "#optional_tools_table"
        table = self.query_one(table_id, DataTable)
        table.add_row(*row, key=tool_id)

    @work
    async def action_install_tool(self) -> None:
        """Install the selected tool."""
        tool_id = self.selected_tool_id
        if not tool_id:
            self.notify("No tool selected", severity="warning")
            return
            
        await self._install_tool(tool_id)

    @work
    async def action_update_tool(self) -> None:
        """Update the selected tool (same as install for now)."""
        tool_id = self.selected_tool_id
        if not tool_id:
            self.notify("No tool selected", severity="warning")
            return
            
        await self._install_tool(tool_id, update=True)

    @work
    async def action_verify_tool(self) -> None:
        """Verify the selected tool."""
        tool_id = self.selected_tool_id
        if not tool_id:
            self.notify("No tool selected", severity="warning")
            return
            
        is_valid = self.installer.verify_tool(tool_id)
        if is_valid:
            self.notify(f"{tool_id} is correctly installed", severity="information")
        else:
            self.notify(f"{tool_id} is missing or broken", severity="error")
        
        # Refresh just this row if possible, or full reload
        _ = self.load_tools()

    @work
    async def action_install_all(self) -> None:
        """Install all missing tools."""
        self.notify("Starting full installation...", severity="information")
        
        # Disable buttons
        self.query("Button").set_class(True, "-disabled")
        
        try:
            results = await self.installer.install_all(skip_errors=True)
            
            failures = [k for k, v in results.items() if isinstance(v, Exception)]
            
            if failures:
                self.notify(f"Failed to install: {', '.join(failures)}", severity="error")
            else:
                self.notify("All tools installed successfully", severity="information")
                
        except Exception as e:
            self.notify(f"Installation failed: {e}", severity="error")
        finally:
            self.query("Button").set_class(False, "-disabled")
            _ = self.load_tools()

    async def _install_tool(self, tool_id: str, update: bool = False) -> None:
        """Internal install handler."""
        action = "Updating" if update else "Installing"
        self.notify(f"{action} {tool_id}...", severity="information")
        
        try:
            await self.installer.install_tool(tool_id)
            self.notify(f"{tool_id} installed successfully", severity="information")
            _ = self.load_tools()
        except ToolInstallError as e:
            self.notify(f"Failed to install {tool_id}: {e}", severity="error")
        except Exception as e:
            self.notify(f"Unexpected error: {e}", severity="error")

    # Button handlers
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn_install":
            self.action_install_tool()
        elif event.button.id == "btn_update":
            self.action_update_tool()
        elif event.button.id == "btn_verify":
            self.action_verify_tool()
        elif event.button.id == "btn_install_all":
            self.action_install_all()
