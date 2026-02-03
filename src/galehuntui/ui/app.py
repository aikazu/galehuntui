from pathlib import Path
from typing import Any, Optional, Type

import yaml

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

from galehuntui.core.config import get_data_dir, get_user_config_path
from galehuntui.storage.database import Database
from galehuntui.ui.themes import GALEHUNT_THEMES


class GaleHunTUIApp(App):

    CSS_PATH = "styles/main.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+shift+t", "cycle_themes", "Cycle Themes"),
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
        self._theme_names = list(GALEHUNT_THEMES.keys())

    def on_mount(self) -> None:
        self.title = "GaleHunTUI"
        
        for theme in GALEHUNT_THEMES.values():
            self.register_theme(theme)
        
        saved_theme = self._load_theme_from_config()
        self.theme = saved_theme
        
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

    def _load_theme_from_config(self) -> str:
        LEGACY_THEME_MAPPING = {
            "Dark": "phantom",
            "Light": "manuscript",
            "System": "phantom",
        }
        DEFAULT_THEME = "phantom"
        
        try:
            config_path = get_user_config_path()
            
            if not config_path.exists():
                return DEFAULT_THEME
            
            with config_path.open("r") as f:
                config = yaml.safe_load(f)
            
            if not config:
                return DEFAULT_THEME
            
            theme_value = config.get("theme", DEFAULT_THEME)
            
            if theme_value in LEGACY_THEME_MAPPING:
                return LEGACY_THEME_MAPPING[theme_value]
            
            if theme_value in GALEHUNT_THEMES:
                return theme_value
            
            return DEFAULT_THEME
            
        except Exception:
            return DEFAULT_THEME

    def action_cycle_themes(self) -> None:
        try:
            current_idx = self._theme_names.index(self.theme)
            next_idx = (current_idx + 1) % len(self._theme_names)
            new_theme = self._theme_names[next_idx]
            
            self.theme = new_theme
            self.notify(f"Theme: {new_theme.title()}")
        except (ValueError, IndexError):
            self.theme = self._theme_names[0]
            self.notify(f"Theme: {self._theme_names[0].title()}")

if __name__ == "__main__":
    app = GaleHunTUIApp()
    app.run()
