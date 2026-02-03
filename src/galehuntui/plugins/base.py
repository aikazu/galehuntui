from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from galehuntui.tools.base import ToolAdapter
    from galehuntui.core.models import ToolConfig, ToolResult


class PluginState(str, Enum):
    DISCOVERED = "discovered"
    VALIDATED = "validated"
    ENABLED = "enabled"
    DISABLED = "disabled"
    FAILED = "failed"


@dataclass
class PluginMetadata:
    name: str
    version: str
    description: str
    author: str = ""
    homepage: str = ""
    license: str = ""
    min_galehuntui_version: str = ""
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "homepage": self.homepage,
            "license": self.license,
            "min_galehuntui_version": self.min_galehuntui_version,
            "dependencies": self.dependencies,
            "tags": self.tags,
        }


class ToolPlugin(ABC):
    metadata: PluginMetadata
    state: PluginState = PluginState.DISCOVERED

    @property
    @abstractmethod
    def tool_name(self) -> str:
        pass

    @abstractmethod
    def get_adapter(self, bin_path: Path) -> ToolAdapter:
        pass

    @abstractmethod
    def get_install_instructions(self) -> dict[str, Any]:
        pass

    def validate_environment(self) -> tuple[bool, str]:
        return True, ""

    def on_load(self) -> None:
        pass

    def on_unload(self) -> None:
        pass

    @classmethod
    def from_module(cls, module: Any) -> Optional[ToolPlugin]:
        if hasattr(module, "create_plugin"):
            return module.create_plugin()
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, ToolPlugin)
                and attr is not ToolPlugin
            ):
                return attr()
        return None
