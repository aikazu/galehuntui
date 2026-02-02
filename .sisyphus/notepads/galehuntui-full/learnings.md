# Learnings & Conventions

## Project Structure
- `src/galehuntui/`: Main source code
- `tools/`: External tools (gitignored)
- `configs/`: Configuration files
- `tests/`: Tests

## Coding Standards
- Use `pathlib` for all file paths
- Use `pydantic` for data models
- Use `asyncio` for async operations
- Max nesting level: 3
- Max function length: 70 lines
- Strict typing required

## Technology Stack
- Python 3.11+
- Textual (TUI)
- Typer (CLI)
- SQLite (DB)
### Initial Project Setup
- Created core directory structure for GaleHunTUI.
- Configured pyproject.toml with Textual, Typer, and other required dependencies.
- Established baseline .gitignore including tool bins and run artifacts.

## Task 2: Core Data Models (COMPLETED)

**File Created:** `src/galehuntui/core/models.py` (334 lines)

**Models Implemented:**
- **Enums** (5 total):
  - `Severity` (CRITICAL, HIGH, MEDIUM, LOW, INFO)
  - `Confidence` (CONFIRMED, FIRM, TENTATIVE)
  - `RunState` (PENDING, RUNNING, PAUSED, COMPLETED, FAILED, CANCELLED)
  - `EngagementMode` (BUG_BOUNTY, AUTHORIZED, AGGRESSIVE)
  - `StepStatus` (PENDING, RUNNING, COMPLETED, FAILED, SKIPPED)

- **Core Models** (9 dataclasses):
  - `Finding` - Security finding with evidence tracking
  - `ToolResult` - Tool execution result with success property
  - `ToolConfig` - Tool execution configuration
  - `ScanProfile` - Pipeline profile with rate limit parsing
  - `RunConfig` - Complete run configuration
  - `RunMetadata` - Run state with progress tracking
  - `PipelineStep` - Individual pipeline step tracking
  - `ScopeConfig` - Target scope validation
  - `ClassificationResult` - URL classification with helper properties

**Key Features:**
- All models use strict typing (dataclass + type hints)
- Property methods for computed values (success, progress_percentage, duration)
- Helper methods for common checks (is_active, is_finished, has_evidence)
- Evidence requirement enforced in Finding model
- Rate limit parsing in ScanProfile
- Path handling uses pathlib.Path

**Validation:** Python syntax check passed ✓

## Task 4: Configuration Loader (COMPLETED)

**File Created:** `src/galehuntui/core/config.py` (264 lines)

**Functions Implemented:**
- `get_config_dir()` - Returns Path to configs directory
- `load_scope_config(scope_file)` - Loads and validates scope YAML
- `load_profile_config(profile_name)` - Loads scan profiles (all or specific)
- `load_modes_config()` - Loads engagement modes configuration
- `get_tool_config_for_mode(modes_config, tool_name, mode)` - Helper for mode-specific tool config

**Configuration Files Created:**
1. `configs/scope.example.yaml`:
   - Target domain specification
   - Allowlist/denylist for hosts
   - Excluded paths and extensions
   
2. `configs/profiles.yaml` (6 profiles):
   - `quick` - Fast recon (3 tools, 50/s)
   - `standard` - Balanced (6 tools, 30/s)
   - `deep` - Full pipeline (9 tools, 10/s)
   - `recon_only` - Passive only (5 tools, 40/s)
   - `injection_focus` - XSS/SQLi testing (4 tools, 10/s)
   - `nuclei_scan` - Template scanning (2 tools, 30/s)

3. `configs/modes.yaml`:
   - 3 engagement modes (bugbounty, authorized, aggressive)
   - Rate limits (global & per-host)
   - Concurrency ranges
   - Feature flags (sqlmap_dump, brute_force, etc.)
   - Per-mode tool configurations for 7 tools

**Key Features:**
- Uses PyYAML for parsing with error handling
- FileNotFoundError and YAMLError wrapped in ConfigError
- Validates required fields and data types
- Returns proper model objects (ScopeConfig, ScanProfile)
- Helper function for mode-specific tool settings
- Comprehensive error messages with available options

**Validation Results:**
- ✓ Scope loading: 3 allowlist, 4 denylist entries
- ✓ Profile loading: All 6 profiles with correct parameters
- ✓ Modes loading: 3 modes with 7 tool configurations
- ✓ Error handling: ProfileNotFoundError, ConfigError work correctly
- ✓ Rate limit parsing: 50/s, 30/s, 10/s extracted properly
- ✓ Tool config helper: Correct per-mode settings retrieved
