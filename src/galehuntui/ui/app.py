from pathlib import Path
from typing import Any, Optional, Type

from textual.app import App
from textual.driver import Driver
from textual.screen import Screen

from galehuntui.ui.screens.home import HomeScreen
from galehuntui.ui.screens.new_run import NewRunScreen
from galehuntui.ui.screens.run_detail import RunDetailScreen
from galehuntui.ui.screens.tools_manager import ToolsManagerScreen
from galehuntui.ui.screens.deps_manager import DepsManagerScreen
from galehuntui.ui.screens.settings import SettingsScreen
from galehuntui.ui.screens.profiles import ProfilesScreen
from galehuntui.ui.screens.scope import ScopeScreen
from galehuntui.ui.screens.finding_detail import FindingDetailScreen
from galehuntui.ui.screens.help import HelpScreen
from galehuntui.ui.screens.setup import SetupWizardScreen

from galehuntui.core.config import get_data_dir
from galehuntui.storage.database import Database


class GaleHunTUIApp(App):

    CSS_PATH = "styles/main.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
        ("question_mark", "push_screen('help')", "Help"),
        ("ctrl+n", "push_screen('new_run')", "New Run"),
        ("ctrl+t", "push_screen('tools_manager')", "Tools"),
        ("ctrl+s", "push_screen('settings')", "Settings"),
    ]

    SCREENS = {
        "home": HomeScreen,
        "new_run": NewRunScreen,
        "run_detail": RunDetailScreen,
        "tools_manager": ToolsManagerScreen,
        "deps_manager": DepsManagerScreen,
        "settings": SettingsScreen,
        "profiles": ProfilesScreen,
        "scope": ScopeScreen,
        "finding_detail": FindingDetailScreen,
        "help": HelpScreen,
        "setup": SetupWizardScreen,
    }

    def __init__(
        self,
        driver_class: Type[Driver] | None = None,
        css_path: str | None = None,
        watch_css: bool = False,
        config_path: Optional[Path] = None,
    ):
        super().__init__(driver_class, css_path, watch_css)
        self.config_path = config_path
        self.db: Database | None = None
        self.current_run_id: Optional[str] = None

    def on_mount(self) -> None:
        self.title = "GaleHunTUI"
        self._init_database()
        self.push_screen("home")

    def _init_database(self) -> None:
        try:
            data_dir = get_data_dir()
            db_path = data_dir / "galehuntui.db"
            self.db = Database(db_path)
            self.db.init_db()
        except Exception:
            self.db = None

if __name__ == "__main__":
    app = GaleHunTUIApp()
    app.run()
