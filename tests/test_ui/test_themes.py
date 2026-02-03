import unittest
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock

from galehuntui.ui.themes import GALEHUNT_THEMES
from galehuntui.ui.app import GaleHunTUIApp


class TestThemeSystem(unittest.TestCase):
    """Test suite for GaleHunTUI theme system."""

    def test_theme_count(self):
        """Test that exactly 10 themes are defined."""
        self.assertEqual(len(GALEHUNT_THEMES), 10)

    def test_theme_names(self):
        """Test that all expected theme names exist."""
        expected_names = {
            "phantom",
            "redteam",
            "matrix",
            "synthwave",
            "midnight",
            "obsidian",
            "aurora",
            "sunset",
            "ocean",
            "manuscript",
        }
        self.assertEqual(set(GALEHUNT_THEMES.keys()), expected_names)

    def test_phantom_defaults(self):
        """Test Phantom theme has correct default colors."""
        phantom = GALEHUNT_THEMES["phantom"]
        self.assertEqual(phantom.name, "phantom")
        self.assertEqual(phantom.primary, "#00f2ea")
        self.assertEqual(phantom.secondary, "#ff0055")
        self.assertEqual(phantom.accent, "#7000ff")
        self.assertEqual(phantom.background, "#0f111a")
        self.assertEqual(phantom.surface, "#1a1c29")
        self.assertEqual(phantom.panel, "#26293b")

    def test_manuscript_light(self):
        """Test Manuscript theme is light mode (bright background)."""
        manuscript = GALEHUNT_THEMES["manuscript"]
        self.assertEqual(manuscript.name, "manuscript")
        self.assertEqual(manuscript.background, "#ffffff")
        self.assertEqual(manuscript.foreground, "#1f2937")

    def test_all_themes_have_border(self):
        """Test that all themes define border variables."""
        for theme_name, theme in GALEHUNT_THEMES.items():
            with self.subTest(theme=theme_name):
                self.assertIsNotNone(theme.variables)
                self.assertIn("border", theme.variables)
                self.assertIn("border-blurred", theme.variables)

    def test_all_themes_have_luminosity_spread(self):
        """Test that all themes define luminosity_spread."""
        for theme_name, theme in GALEHUNT_THEMES.items():
            with self.subTest(theme=theme_name):
                self.assertEqual(theme.luminosity_spread, 0.15)

    def test_all_themes_have_required_colors(self):
        """Test that all themes define required semantic colors."""
        required_attrs = [
            "primary",
            "secondary",
            "accent",
            "foreground",
            "background",
            "surface",
            "panel",
            "success",
            "warning",
            "error",
        ]
        
        for theme_name, theme in GALEHUNT_THEMES.items():
            with self.subTest(theme=theme_name):
                for attr in required_attrs:
                    self.assertTrue(hasattr(theme, attr))
                    value = getattr(theme, attr)
                    self.assertIsNotNone(value)
                    # Should be hex color
                    self.assertTrue(value.startswith("#"))

    def test_config_migration_legacy_dark(self):
        """Test config migration maps legacy 'Dark' to 'phantom'."""
        yaml_content = "theme: Dark\n"
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.open", mock_open(read_data=yaml_content)):
                app = GaleHunTUIApp()
                theme = app._load_theme_from_config()
                self.assertEqual(theme, "phantom")

    def test_config_migration_legacy_light(self):
        """Test config migration maps legacy 'Light' to 'manuscript'."""
        yaml_content = "theme: Light\n"
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.open", mock_open(read_data=yaml_content)):
                app = GaleHunTUIApp()
                theme = app._load_theme_from_config()
                self.assertEqual(theme, "manuscript")

    def test_config_migration_legacy_system(self):
        """Test config migration maps legacy 'System' to 'phantom'."""
        yaml_content = "theme: System\n"
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.open", mock_open(read_data=yaml_content)):
                app = GaleHunTUIApp()
                theme = app._load_theme_from_config()
                self.assertEqual(theme, "phantom")

    def test_config_migration_valid_theme(self):
        """Test config migration preserves valid theme names."""
        yaml_content = "theme: redteam\n"
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.open", mock_open(read_data=yaml_content)):
                app = GaleHunTUIApp()
                theme = app._load_theme_from_config()
                self.assertEqual(theme, "redteam")

    def test_config_migration_invalid_theme(self):
        """Test config migration defaults to 'phantom' for invalid themes."""
        yaml_content = "theme: nonexistent\n"
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.open", mock_open(read_data=yaml_content)):
                app = GaleHunTUIApp()
                theme = app._load_theme_from_config()
                self.assertEqual(theme, "phantom")

    def test_config_migration_missing_file(self):
        """Test config migration defaults to 'phantom' when file missing."""
        with patch("pathlib.Path.exists", return_value=False):
            app = GaleHunTUIApp()
            theme = app._load_theme_from_config()
            self.assertEqual(theme, "phantom")

    def test_config_migration_empty_config(self):
        """Test config migration defaults to 'phantom' for empty config."""
        yaml_content = ""
        
        with patch("pathlib.Path.exists", return_value=True):
            with patch("pathlib.Path.open", mock_open(read_data=yaml_content)):
                app = GaleHunTUIApp()
                theme = app._load_theme_from_config()
                self.assertEqual(theme, "phantom")

    def test_cycle_themes(self):
        """Test theme cycling advances through theme list."""
        app = GaleHunTUIApp()
        app._theme_names = ["phantom", "redteam", "matrix"]
        
        # Register themes before setting
        for theme_name in app._theme_names:
            app.register_theme(GALEHUNT_THEMES[theme_name])
        
        app.theme = "phantom"
        
        # Mock notify to prevent actual notification
        app.notify = MagicMock()
        
        # Cycle forward
        app.action_cycle_themes()
        self.assertEqual(app.theme, "redteam")
        app.notify.assert_called_once()
        
        # Cycle forward again
        app.notify.reset_mock()
        app.action_cycle_themes()
        self.assertEqual(app.theme, "matrix")
        
        # Cycle wraps around
        app.notify.reset_mock()
        app.action_cycle_themes()
        self.assertEqual(app.theme, "phantom")

    def test_cycle_themes_single_theme(self):
        """Test theme cycling works with single theme."""
        app = GaleHunTUIApp()
        app._theme_names = ["phantom"]
        
        # Register theme before setting
        app.register_theme(GALEHUNT_THEMES["phantom"])
        
        app.theme = "phantom"
        app.notify = MagicMock()
        
        app.action_cycle_themes()
        self.assertEqual(app.theme, "phantom")

    def test_theme_initialization(self):
        """Test that app initializes with theme list."""
        app = GaleHunTUIApp()
        self.assertEqual(app._theme_names, list(GALEHUNT_THEMES.keys()))
        self.assertEqual(len(app._theme_names), 10)

    def test_all_themes_unique_names(self):
        """Test that all theme names are unique."""
        theme_names = [theme.name for theme in GALEHUNT_THEMES.values()]
        self.assertEqual(len(theme_names), len(set(theme_names)))


if __name__ == "__main__":
    unittest.main()
