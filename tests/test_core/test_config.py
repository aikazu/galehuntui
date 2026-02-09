"""Unit tests for configuration persistence helpers."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from galehuntui.core.config import load_profile_config, save_profiles_config
from galehuntui.core.models import ScanProfile


class TestProfileConfigPersistence(unittest.TestCase):
    """Test loading and saving profile configuration."""

    def test_save_profiles_config_roundtrip(self) -> None:
        """Saving profiles should be readable by load_profile_config."""
        with TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir)

            profiles = {
                "quick": ScanProfile(
                    name="Quick",
                    description="Quick profile",
                    steps=["subfinder", "httpx"],
                    concurrency=8,
                    rate_limit="25/s",
                    timeout=300,
                    use_cases=["fast checks"],
                ),
                "deep": ScanProfile(
                    name="Deep",
                    description="Deep profile",
                    steps=["subfinder", "dnsx", "httpx", "nuclei"],
                    concurrency=4,
                    rate_limit="10/s",
                    timeout=1200,
                ),
            }

            with patch("galehuntui.core.config.get_config_dir", return_value=config_dir):
                save_profiles_config(profiles)
                loaded_profiles = load_profile_config()

            self.assertIsInstance(loaded_profiles, dict)
            self.assertEqual(sorted(loaded_profiles.keys()), ["deep", "quick"])

            quick = loaded_profiles["quick"]
            self.assertEqual(quick.name, "quick")
            self.assertEqual(quick.rate_limit, "25/s")
            self.assertEqual(quick.use_cases, ["fast checks"])

            deep = loaded_profiles["deep"]
            self.assertEqual(deep.description, "Deep profile")
            self.assertEqual(deep.steps, ["subfinder", "dnsx", "httpx", "nuclei"])
