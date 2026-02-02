"""Configuration loader for GaleHunTUI.

This module provides functions to load and validate YAML configuration files
for scopes, profiles, and engagement modes.
"""

from pathlib import Path
from typing import Any

import yaml

from galehuntui.core.exceptions import ConfigError, InvalidScopeError, ProfileNotFoundError
from galehuntui.core.constants import EngagementMode, DEFAULTS
from galehuntui.core.models import (
    ScanProfile,
    ScopeConfig,
)


# ============================================================================
# Configuration Paths
# ============================================================================

def get_config_dir() -> Path:
    """Get the configuration directory path.
    
    Returns:
        Path to configs directory (./configs relative to project root)
    """
    # Get project root (3 levels up from this file: core/ -> galehuntui/ -> src/ -> root)
    project_root = Path(__file__).parent.parent.parent.parent
    return project_root / "configs"


# ============================================================================
# Scope Configuration Loader
# ============================================================================

def load_scope_config(scope_file: Path | str | None = None) -> ScopeConfig:
    """Load scope configuration from YAML file.
    
    Args:
        scope_file: Path to scope YAML file. If None, loads scope.example.yaml
        
    Returns:
        ScopeConfig object with validated scope settings
        
    Raises:
        ConfigError: If file not found or YAML parsing fails
        InvalidScopeError: If scope configuration is invalid
    """
    if scope_file is None:
        scope_path = get_config_dir() / "scope.example.yaml"
    else:
        scope_path = Path(scope_file)
    
    if not scope_path.exists():
        raise ConfigError(f"Scope file not found: {scope_path}")
    
    try:
        with scope_path.open("r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse scope YAML: {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read scope file: {e}") from e
    
    if not data:
        raise InvalidScopeError("Scope configuration is empty")
    
    if "target" not in data:
        raise InvalidScopeError("Missing 'target' section in scope config")
    
    if "domain" not in data["target"]:
        raise InvalidScopeError("Missing 'domain' in target section")
    
    target_domain = data["target"]["domain"]
    
    scope_data = data.get("scope", {})
    allowlist = scope_data.get("allowlist", [])
    denylist = scope_data.get("denylist", [])
    
    exclusions = scope_data.get("exclusions", {})
    excluded_paths = exclusions.get("paths", [])
    excluded_extensions = exclusions.get("extensions", [])
    
    if not isinstance(allowlist, list):
        raise InvalidScopeError("'allowlist' must be a list")
    if not isinstance(denylist, list):
        raise InvalidScopeError("'denylist' must be a list")
    if not isinstance(excluded_paths, list):
        raise InvalidScopeError("'exclusions.paths' must be a list")
    if not isinstance(excluded_extensions, list):
        raise InvalidScopeError("'exclusions.extensions' must be a list")
    
    return ScopeConfig(
        target_domain=target_domain,
        allowlist=allowlist,
        denylist=denylist,
        excluded_paths=excluded_paths,
        excluded_extensions=excluded_extensions,
    )


# ============================================================================
# Profile Configuration Loader
# ============================================================================

def load_profile_config(profile_name: str | None = None) -> ScanProfile | dict[str, ScanProfile]:
    """Load scan profile(s) from YAML configuration.
    
    Args:
        profile_name: Name of specific profile to load. If None, loads all profiles
        
    Returns:
        ScanProfile if profile_name specified, or dict of all profiles if None
        
    Raises:
        ConfigError: If file not found or YAML parsing fails
        ProfileNotFoundError: If specified profile doesn't exist
    """
    profiles_path = get_config_dir() / "profiles.yaml"
    
    if not profiles_path.exists():
        raise ConfigError(f"Profiles file not found: {profiles_path}")
    
    try:
        with profiles_path.open("r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse profiles YAML: {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read profiles file: {e}") from e
    
    if not data or "profiles" not in data:
        raise ConfigError("Profiles configuration is empty or missing 'profiles' section")
    
    profiles_data = data["profiles"]
    
    profiles: dict[str, ScanProfile] = {}
    
    for name, config in profiles_data.items():
        if not isinstance(config, dict):
            raise ConfigError(f"Invalid profile configuration for '{name}'")
        
        required_fields = ["description", "steps"]
        for field in required_fields:
            if field not in config:
                raise ConfigError(f"Missing required field '{field}' in profile '{name}'")
        
        profile = ScanProfile(
            name=name,
            description=config["description"],
            steps=config["steps"],
            concurrency=config.get("concurrency", DEFAULTS["concurrency"]),
            rate_limit=config.get("rate_limit", DEFAULTS["rate_limit"]),
            timeout=config.get("timeout", DEFAULTS["timeout"]),
            use_cases=config.get("use_cases", []),
        )
        profiles[name] = profile
    
    if profile_name is not None:
        if profile_name not in profiles:
            available = ", ".join(profiles.keys())
            raise ProfileNotFoundError(
                f"Profile '{profile_name}' not found. Available profiles: {available}"
            )
        return profiles[profile_name]
    
    return profiles


# ============================================================================
# Modes Configuration Loader
# ============================================================================

def load_modes_config() -> dict[str, Any]:
    """Load engagement modes configuration from YAML.
    
    Returns:
        Dictionary containing mode-specific settings for tools and rate limits
        
    Raises:
        ConfigError: If file not found or YAML parsing fails
    """
    modes_path = get_config_dir() / "modes.yaml"
    
    if not modes_path.exists():
        raise ConfigError(f"Modes file not found: {modes_path}")
    
    try:
        with modes_path.open("r") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse modes YAML: {e}") from e
    except OSError as e:
        raise ConfigError(f"Failed to read modes file: {e}") from e
    
    if not data:
        raise ConfigError("Modes configuration is empty")
    
    expected_modes = [mode.value for mode in EngagementMode]
    
    if "modes" not in data:
        raise ConfigError("Missing 'modes' section in modes configuration")
    
    modes_data = data["modes"]
    
    for mode in expected_modes:
        if mode not in modes_data:
            raise ConfigError(f"Missing configuration for engagement mode: {mode}")
    
    return data


# ============================================================================
# Tool Configuration Helper
# ============================================================================

def get_tool_config_for_mode(
    modes_config: dict[str, Any],
    tool_name: str,
    mode: EngagementMode,
) -> dict[str, Any]:
    """Get tool-specific configuration for a given engagement mode.
    
    Args:
        modes_config: Full modes configuration dictionary
        tool_name: Name of the tool
        mode: Engagement mode
        
    Returns:
        Dictionary with tool configuration for the specified mode
        
    Raises:
        ConfigError: If tool or mode configuration is missing
    """
    if "tools" not in modes_config:
        return {}
    
    tools = modes_config["tools"]
    
    if tool_name not in tools:
        return {}
    
    tool_config = tools[tool_name]
    
    if "per_mode" in tool_config:
        per_mode = tool_config["per_mode"]
        if mode.value in per_mode:
            return per_mode[mode.value]
    
    return {k: v for k, v in tool_config.items() if k != "per_mode"}
