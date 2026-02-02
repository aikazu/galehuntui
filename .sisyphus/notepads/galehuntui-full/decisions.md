# Architectural Decisions

- **Runner Strategy**: Docker preferred, Local fallback
- **Concurrency**: Single scan + queue
- **Process Model**: Detached (scan survives TUI exit)
- **Config Location**: `./configs/` (project root)
- **Tool Installation**: Project-local `./tools/bin/`
