from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from galehuntui.plugins.base import ToolPlugin, PluginMetadata, PluginState


logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "galehuntui.plugins.tools"


@dataclass
class PluginInfo:
    plugin: ToolPlugin
    source: str
    path: Optional[Path] = None
    error: Optional[str] = None


@dataclass
class PluginManagerConfig:
    plugin_dir: Path = field(
        default_factory=lambda: Path.home() / ".local" / "share" / "galehuntui" / "plugins"
    )
    enabled_plugins: list[str] = field(default_factory=list)
    disabled_plugins: list[str] = field(default_factory=list)
    auto_discover: bool = True


class PluginManager:
    def __init__(self, config: Optional[PluginManagerConfig] = None) -> None:
        self.config = config or PluginManagerConfig()
        self._plugins: dict[str, PluginInfo] = {}
        self._discovered = False

    def discover(self) -> list[str]:
        if self._discovered:
            return list(self._plugins.keys())

        discovered = []

        entry_point_plugins = self._discover_entry_points()
        discovered.extend(entry_point_plugins)

        if self.config.plugin_dir.exists():
            dir_plugins = self._discover_directory(self.config.plugin_dir)
            discovered.extend(dir_plugins)

        self._discovered = True
        logger.info(f"Discovered {len(discovered)} plugins")
        return discovered

    def _discover_entry_points(self) -> list[str]:
        discovered = []

        try:
            if sys.version_info >= (3, 10):
                from importlib.metadata import entry_points
                eps = entry_points(group=ENTRY_POINT_GROUP)
            else:
                from importlib.metadata import entry_points
                all_eps = entry_points()
                eps = all_eps.get(ENTRY_POINT_GROUP, [])

            for ep in eps:
                try:
                    plugin_class = ep.load()
                    if isinstance(plugin_class, type) and issubclass(plugin_class, ToolPlugin):
                        plugin = plugin_class()
                    elif callable(plugin_class):
                        plugin = plugin_class()
                    else:
                        continue

                    if not isinstance(plugin, ToolPlugin):
                        continue

                    name = plugin.metadata.name
                    self._plugins[name] = PluginInfo(
                        plugin=plugin,
                        source="entry_point",
                    )
                    plugin.state = PluginState.DISCOVERED
                    discovered.append(name)
                    logger.debug(f"Discovered plugin from entry point: {name}")

                except Exception as e:
                    logger.warning(f"Failed to load entry point {ep.name}: {e}")

        except Exception as e:
            logger.warning(f"Failed to discover entry points: {e}")

        return discovered

    def _discover_directory(self, plugin_dir: Path) -> list[str]:
        discovered = []

        for item in plugin_dir.iterdir():
            if item.is_file() and item.suffix == ".py":
                plugin = self._load_plugin_file(item)
                if plugin:
                    name = plugin.metadata.name
                    self._plugins[name] = PluginInfo(
                        plugin=plugin,
                        source="directory",
                        path=item,
                    )
                    plugin.state = PluginState.DISCOVERED
                    discovered.append(name)
                    logger.debug(f"Discovered plugin from file: {name}")

            elif item.is_dir() and (item / "__init__.py").exists():
                plugin = self._load_plugin_package(item)
                if plugin:
                    name = plugin.metadata.name
                    self._plugins[name] = PluginInfo(
                        plugin=plugin,
                        source="directory",
                        path=item,
                    )
                    plugin.state = PluginState.DISCOVERED
                    discovered.append(name)
                    logger.debug(f"Discovered plugin from package: {name}")

        return discovered

    def _load_plugin_file(self, path: Path) -> Optional[ToolPlugin]:
        try:
            spec = importlib.util.spec_from_file_location(path.stem, path)
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            return ToolPlugin.from_module(module)

        except Exception as e:
            logger.warning(f"Failed to load plugin from {path}: {e}")
            return None

    def _load_plugin_package(self, path: Path) -> Optional[ToolPlugin]:
        try:
            package_name = f"galehuntui_plugin_{path.name}"

            spec = importlib.util.spec_from_file_location(
                package_name,
                path / "__init__.py",
                submodule_search_locations=[str(path)],
            )
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[package_name] = module
            spec.loader.exec_module(module)

            return ToolPlugin.from_module(module)

        except Exception as e:
            logger.warning(f"Failed to load plugin package from {path}: {e}")
            return None

    def validate(self, name: str) -> tuple[bool, str]:
        if name not in self._plugins:
            return False, f"Plugin not found: {name}"

        info = self._plugins[name]
        plugin = info.plugin

        valid, message = plugin.validate_environment()
        if valid:
            plugin.state = PluginState.VALIDATED
        else:
            plugin.state = PluginState.FAILED
            info.error = message

        return valid, message

    def validate_all(self) -> dict[str, tuple[bool, str]]:
        results = {}
        for name in self._plugins:
            results[name] = self.validate(name)
        return results

    def enable(self, name: str) -> bool:
        if name not in self._plugins:
            logger.warning(f"Plugin not found: {name}")
            return False

        info = self._plugins[name]
        plugin = info.plugin

        if plugin.state == PluginState.FAILED:
            logger.warning(f"Cannot enable failed plugin: {name}")
            return False

        if plugin.state not in (PluginState.VALIDATED, PluginState.DISABLED):
            valid, message = self.validate(name)
            if not valid:
                logger.warning(f"Plugin validation failed: {message}")
                return False

        try:
            plugin.on_load()
            plugin.state = PluginState.ENABLED

            if name in self.config.disabled_plugins:
                self.config.disabled_plugins.remove(name)
            if name not in self.config.enabled_plugins:
                self.config.enabled_plugins.append(name)

            logger.info(f"Enabled plugin: {name}")
            return True

        except Exception as e:
            plugin.state = PluginState.FAILED
            info.error = str(e)
            logger.error(f"Failed to enable plugin {name}: {e}")
            return False

    def disable(self, name: str) -> bool:
        if name not in self._plugins:
            logger.warning(f"Plugin not found: {name}")
            return False

        info = self._plugins[name]
        plugin = info.plugin

        if plugin.state != PluginState.ENABLED:
            logger.warning(f"Plugin not enabled: {name}")
            return False

        try:
            plugin.on_unload()
            plugin.state = PluginState.DISABLED

            if name in self.config.enabled_plugins:
                self.config.enabled_plugins.remove(name)
            if name not in self.config.disabled_plugins:
                self.config.disabled_plugins.append(name)

            logger.info(f"Disabled plugin: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to disable plugin {name}: {e}")
            return False

    def get_plugin(self, name: str) -> Optional[ToolPlugin]:
        info = self._plugins.get(name)
        return info.plugin if info else None

    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        return self._plugins.get(name)

    def list_plugins(self) -> list[PluginMetadata]:
        return [info.plugin.metadata for info in self._plugins.values()]

    def list_enabled(self) -> list[str]:
        return [
            name for name, info in self._plugins.items()
            if info.plugin.state == PluginState.ENABLED
        ]

    def get_tool_adapter(self, tool_name: str, bin_path: Path) -> Optional[Any]:
        for info in self._plugins.values():
            if info.plugin.state == PluginState.ENABLED:
                if info.plugin.tool_name == tool_name:
                    return info.plugin.get_adapter(bin_path)
        return None

    def register(self, plugin: ToolPlugin, source: str = "manual") -> bool:
        name = plugin.metadata.name
        if name in self._plugins:
            logger.warning(f"Plugin already registered: {name}")
            return False

        self._plugins[name] = PluginInfo(
            plugin=plugin,
            source=source,
        )
        plugin.state = PluginState.DISCOVERED
        logger.info(f"Registered plugin: {name}")
        return True

    def unregister(self, name: str) -> bool:
        if name not in self._plugins:
            return False

        info = self._plugins[name]
        if info.plugin.state == PluginState.ENABLED:
            self.disable(name)

        del self._plugins[name]
        logger.info(f"Unregistered plugin: {name}")
        return True
