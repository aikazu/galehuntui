# Architectural Decisions

- **Runner Strategy**: Docker preferred, Local fallback
- **Concurrency**: Single scan + queue
- **Process Model**: Detached (scan survives TUI exit)
- **Config Location**: `./configs/` (project root)
- **Tool Installation**: Project-local `./tools/bin/`
- **Setup Wizard**: Implemented as a stateful screen with mocked system operations for the UI prototype, using Textual's `ContentSwitcher` and `Worker` pattern for async tasks.
