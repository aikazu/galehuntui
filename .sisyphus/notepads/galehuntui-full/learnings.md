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
