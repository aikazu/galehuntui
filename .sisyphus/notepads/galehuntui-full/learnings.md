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
