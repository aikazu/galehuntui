from typing import Type

from textual.app import App, CSSPathType
from textual.driver import Driver
from textual.screen import Screen

# Import screens
from galehuntui.ui.screens.home import HomeScreen
from galehuntui.ui.screens.new_run import NewRunScreen
from galehuntui.ui.screens.run_detail import RunDetailScreen
from galehuntui.ui.screens.tools_manager import ToolsManagerScreen
from galehuntui.ui.screens.deps_manager import DependenciesManagerScreen
from galehuntui.ui.screens.settings import SettingsScreen
from galehuntui.ui.screens.profiles import ProfilesScreen
from galehuntui.ui.screens.scope import ScopeScreen
from galehuntui.ui.screens.finding_detail import FindingDetailScreen
from galehuntui.ui.screens.help import HelpScreen
from galehuntui.ui.screens.setup import SetupScreen

# Core components (placeholders for initialization)
from galehuntui.core.config import Config
from galehuntui.storage.database import Database

class GaleHunTUIApp(App):
    """
    GaleHunTUI - Terminal-based Automated Web Pentesting Application
    """

    CSS_PATH = "styles/main.tcss"

    BINDINGS = [
        # Global bindings
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("question_mark", "push_screen('help')", "Help"),
        
        # Navigation
        ("ctrl+n", "push_screen('new_run')", "New Run"),
        ("ctrl+t", "push_screen('tools_manager')", "Tools"),
        ("ctrl+s", "push_screen('settings')", "Settings"),
    ]

    SCREENS = {
        "home": HomeScreen,
        "new_run": NewRunScreen,
        "run_detail": RunDetailScreen,
        "tools_manager": ToolsManagerScreen,
        "deps_manager": DependenciesManagerScreen,
        "settings": SettingsScreen,
        "profiles": ProfilesScreen,
        "scope": ScopeScreen,
        "finding_detail": FindingDetailScreen,
        "help": HelpScreen,
        "setup": SetupScreen,
    }

    def __init__(
        self,
        driver_class: Type[Driver] | None = None,
        css_path: CSSPathType | None = None,
        watch_css: bool = False,
    ):
        super().__init__(driver_class, css_path, watch_css)
        self.db: Database | None = None
        self.config_manager: Config | None = None

    def on_mount(self) -> None:
        """Initialize application state and push the home screen."""
        self.title = "GaleHunTUI"
        
        # Initialize Core Systems
        # Note: In a real scenario, we might want to do this async or with a splash screen
        # self._init_database()
        
        # Push the home screen
        self.push_screen("home")

    def _init_database(self) -> None:
        """Initialize the database connection."""
        # self.db = Database()
        # self.db.connect()
        pass

if __name__ == "__main__":
    app = GaleHunTUIApp()
    app.run()
