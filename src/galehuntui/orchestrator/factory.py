"""Factory helpers for building pipeline orchestrator instances."""

import logging
from pathlib import Path
from typing import Callable, Optional

from galehuntui.core.config import get_data_dir, load_profile_config, load_scope_config
from galehuntui.core.constants import EngagementMode
from galehuntui.core.models import ScanProfile, ScopeConfig
from galehuntui.orchestrator.pipeline import PipelineOrchestrator
from galehuntui.orchestrator.state import RunStateManager
from galehuntui.storage.database import Database
from galehuntui.tools.adapters import (
    DalfoxAdapter,
    DnsxAdapter,
    FfufAdapter,
    GauAdapter,
    HttpxAdapter,
    KatanaAdapter,
    NucleiAdapter,
    SqlmapAdapter,
    SubfinderAdapter,
)
from galehuntui.tools.base import ToolAdapter


logger = logging.getLogger(__name__)


AdapterFactory = Callable[[Path], ToolAdapter]


ADAPTER_CLASSES: dict[str, AdapterFactory] = {
    "subfinder": SubfinderAdapter,
    "dnsx": DnsxAdapter,
    "httpx": HttpxAdapter,
    "katana": KatanaAdapter,
    "gau": GauAdapter,
    "nuclei": NucleiAdapter,
    "dalfox": DalfoxAdapter,
    "ffuf": FfufAdapter,
    "sqlmap": SqlmapAdapter,
}


def load_tool_adapters(steps: list[str], tools_dir: Path) -> dict[str, ToolAdapter]:
    """Instantiate tool adapters required for scan steps."""
    adapters: dict[str, ToolAdapter] = {}
    bin_dir = tools_dir / "bin"

    for tool_name in steps:
        adapter_class = ADAPTER_CLASSES.get(tool_name)
        if adapter_class is None:
            logger.debug("No adapter class registered for tool: %s", tool_name)
            continue

        try:
            adapters[tool_name] = adapter_class(bin_dir)
        except (OSError, ValueError, TypeError) as exc:
            logger.warning("Failed to initialize adapter %s: %s", tool_name, exc)

    return adapters


def load_scan_profile(profile_name: str) -> ScanProfile:
    """Load a single scan profile by name."""
    profile = load_profile_config(profile_name)
    if not isinstance(profile, ScanProfile):
        raise ValueError(f"Invalid profile configuration for '{profile_name}'")
    return profile


def create_pipeline_orchestrator(
    *,
    target: str,
    profile_name: str,
    engagement_mode: EngagementMode,
    db: Database,
    scope_file: Optional[Path | str] = None,
    scope_config: Optional[ScopeConfig] = None,
    tools_dir: Optional[Path] = None,
    run_id: Optional[str] = None,
    runs_base_dir: Optional[Path] = None,
) -> PipelineOrchestrator:
    """Build a configured pipeline orchestrator for CLI/TUI usage."""
    profile = load_scan_profile(profile_name)

    if scope_config is None:
        if scope_file is None:
            scope_config = ScopeConfig(
                target_domain=target,
                allowlist=[f"*.{target}", target],
                denylist=[],
            )
        else:
            scope_config = load_scope_config(scope_file)

    resolved_tools_dir = tools_dir or (Path.cwd() / "tools")
    adapters = load_tool_adapters(profile.steps, resolved_tools_dir)

    orchestrator = PipelineOrchestrator.create_standard_pipeline(
        adapters=adapters,
        target=target,
        profile=profile,
        scope=scope_config,
        engagement_mode=engagement_mode,
    )
    orchestrator.db = db

    base_dir = runs_base_dir or (get_data_dir() / "runs")
    orchestrator.state = RunStateManager(
        orchestrator.run_config,
        run_id=run_id,
        base_dir=base_dir,
        db=db,
    )

    return orchestrator
