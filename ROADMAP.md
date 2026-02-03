# GaleHunTUI Development Roadmap

> **Version**: 1.0.0  
> **Last Updated**: 2026-02-03  
> **Status**: ✅ COMPLETE - All Waves Implemented

---

## Executive Summary

This roadmap outlined 10 planned enhancements for GaleHunTUI, organized into 5 implementation waves based on technical dependencies and user value. **All waves have been successfully implemented.**

### At a Glance

| Wave | Focus | Duration | Key Deliverables | Status |
|------|-------|----------|------------------|--------|
| **Wave 0** | Quick Win | 1 day | Tool installation works | ✅ Complete |
| **Wave 1** | Foundation | 1-2 weeks | Dependency management complete | ✅ Complete |
| **Wave 2** | Reliability | 2-3 weeks | Scan resume capability | ✅ Complete |
| **Wave 3** | User Experience | 2 weeks | Enhanced TUI widgets | ✅ Complete |
| **Wave 4** | Ecosystem | 3-4 weeks | Plugins & notifications | ✅ Complete |

**Total Estimated Effort**: 8-12 weeks

---

## Priority Matrix

| Priority | Item | Effort | Wave | Value | Status |
|----------|------|--------|------|-------|--------|
| P0 | `tools/registry.yaml` | Small | 0 | Critical | ✅ Complete |
| P0 | `tools/deps/manager.py` | Medium | 1 | Critical | ✅ Complete |
| P0 | `tools/deps/wordlists.py` | Small | 1 | High | ✅ Complete |
| P0 | `tools/deps/templates.py` | Small | 1 | High | ✅ Complete |
| P1 | `storage/migrations/` | Medium | 2 | High | ✅ Complete |
| P1 | Resume Capability | Large | 2 | High | ✅ Complete |
| P2 | `ui/widgets/log_view.py` | Medium | 3 | Medium | ✅ Complete |
| P2 | `ui/widgets/progress.py` | Medium | 3 | Medium | ✅ Complete |
| P2 | `ui/widgets/findings_table.py` | Medium | 3 | Medium | ✅ Complete |
| P3 | Webhook Notifications | Medium | 4 | Medium | ✅ Complete |
| P3 | Plugin System | Large | 4 | High | ✅ Complete |

---

## Dependency Graph

```
Wave 0: Quick Win (START HERE)
└── registry.yaml ─────────────────────────────────────┐
                                                       │
Wave 1: Foundation                                     │
├── deps/registry.yaml ────────────────────────────────┤
├── deps/wordlists.py ─────────────────────────────────┼──→ deps/manager.py
└── deps/templates.py ─────────────────────────────────┘

Wave 2: Infrastructure
└── storage/migrations/ ──────────────────────────────→ Resume Capability

Wave 3: User Experience (All parallelizable)
├── log_view.py
├── progress.py
└── findings_table.py

Wave 4: Ecosystem (Independent of each other)
├── Webhook Notifications
└── Plugin System (Tool Adapters Only)
```

---

## Test Strategy

| Component | Strategy | Rationale |
|-----------|----------|-----------|
| `storage/migrations/` | TDD | Data integrity critical |
| Resume capability | TDD | State management complex |
| `tools/deps/manager.py` | TDD | External I/O involved |
| Webhook notifications | TDD | Network reliability matters |
| Plugin system | TDD | Security implications |
| TUI widgets | Tests After | Visual feedback needed during dev |

---

## Wave 0: Quick Win

**Timeline**: 1 day  
**Goal**: Unblock tool installation immediately

### 0.1 Tool Registry (`tools/registry.yaml`)

**Priority**: P0 (Critical - Blocking)  
**Effort**: Small (2-4 hours)  
**Dependencies**: None  
**Blocks**: All tool installation, dependency managers

#### Problem Statement

The `installer.py` module (lines 67-84, 390-415) expects a `registry.yaml` file to exist, but it doesn't. This means `galehuntui tools install --all` fails immediately.

#### Technical Approach

Create `src/galehuntui/tools/registry.yaml` with entries for all 11 supported tools.

#### Success Criteria

- [x] `galehuntui tools list` displays all 11 tools with their status
- [x] `galehuntui tools install subfinder` downloads and installs successfully
- [x] `galehuntui tools install --all` completes without errors
- [x] `galehuntui tools verify` reports accurate tool availability
- [x] Existing `installer.py` code works without modification

---

## Wave 1: Foundation & Infrastructure

**Timeline**: 1-2 weeks  
**Goal**: Complete dependency management system

### 1.1 Dependency Registry (`tools/deps/registry.yaml`)

**Priority**: P0 (Critical)  
**Effort**: Small (2-4 hours)  
**Dependencies**: Wave 0 complete (registry.yaml pattern established)  
**Blocks**: Dependency manager implementation

### 1.2 Dependency Manager (`tools/deps/manager.py`)

**Priority**: P0 (Critical)  
**Effort**: Medium (1-2 days)  
**Dependencies**: deps/registry.yaml  
**Blocks**: TUI deps_manager screen functionality

#### Current State

- `tools/deps/__init__.py` is empty (stub only)
- `ui/screens/deps_manager.py` uses a **mock** `DependencyManager`
- UI expects interface: `get_dependencies()`, `install()`, `update()`, `verify()`

#### Success Criteria

- [x] `galehuntui deps list` shows all dependencies with real status
- [x] `galehuntui deps install nuclei-templates` clones repository
- [x] `galehuntui deps update --all` pulls latest for all installed deps
- [x] `galehuntui deps verify` reports accurate installation status
- [x] TUI deps_manager screen shows real data (not mock)
- [x] Unit tests cover install, update, verify operations

### 1.3 Wordlists Module (`tools/deps/wordlists.py`)

**Priority**: P0 (High)  
**Effort**: Small (2-4 hours)  
**Dependencies**: deps/manager.py  

#### Success Criteria

- [x] `WordlistManager.get_wordlist("directories")` returns correct path
- [x] Custom wordlist paths resolved correctly
- [x] Integration with ffuf/wfuzz adapters

### 1.4 Templates Module (`tools/deps/templates.py`)

**Priority**: P0 (High)  
**Effort**: Small (2-4 hours)  
**Dependencies**: deps/manager.py  

#### Success Criteria

- [x] `TemplateManager.get_template_path()` returns nuclei-templates location
- [x] Integration with nuclei adapter
- [x] Template filtering by severity/tag

---

## Wave 2: Reliability & Robustness

**Timeline**: 2-3 weeks  
**Goal**: Enable scan resume after interruption

### 2.1 Database Migrations (`storage/migrations/`)

**Priority**: P1 (High)  
**Effort**: Medium (2-3 days)  
**Dependencies**: None  
**Blocks**: Resume capability, all future schema changes

#### Current State

- `database.py` uses `CREATE TABLE IF NOT EXISTS` (no version tracking)
- No way to evolve schema without breaking existing databases
- Current schema: `runs` table, `findings` table

#### Technical Approach

**Recommended**: Custom lightweight migration system (not Alembic)
- Alembic has async limitations with SQLite
- Simple integer-versioned migrations with checksum verification

#### Success Criteria

- [x] `schema_migrations` table tracks applied versions
- [x] Fresh install runs all migrations automatically
- [x] Existing databases upgrade seamlessly (no data loss)
- [x] Rollback works for reversible migrations
- [x] `Database.init_db()` uses migration runner
- [x] Tests verify migration up/down operations

### 2.2 Resume Capability

**Priority**: P1 (High)  
**Effort**: Large (3-5 days)  
**Dependencies**: Database migrations (2.1)  
**Blocks**: None

#### Current State

- `RunStateManager` tracks `PipelineStep` objects **in memory only**
- Database saves only aggregate counts (`completed_steps`, `failed_steps`)
- **Problem**: If app crashes, step-level progress is **lost forever**
- Cannot determine which specific steps completed

#### Success Criteria

- [x] Step completion persisted immediately to `run_steps` table
- [x] `galehuntui runs list` shows run state (completed/interrupted/running)
- [x] `galehuntui run example.com --resume run-xxx` resumes from last step
- [x] TUI shows "Resume" option for interrupted runs
- [x] Skipped steps logged clearly during resume
- [x] Tests simulate crash-and-resume scenarios

---

## Wave 3: User Experience

**Timeline**: 2 weeks  
**Goal**: Enhanced TUI widgets for better visibility

> **Note**: All three widgets can be developed in parallel.

### 3.1 Log View Widget (`ui/widgets/log_view.py`)

**Priority**: P2 (Medium)  
**Effort**: Medium (1-2 days)  
**Dependencies**: None  
**Can Parallelize**: Yes

#### Success Criteria

- [x] Logs display with severity-based coloring
- [x] Filter by minimum severity level (e.g., show HIGH+ only)
- [x] Search/highlight functionality
- [x] Export visible logs to file
- [x] Keyboard shortcuts work

### 3.2 Progress Widget (`ui/widgets/progress.py`)

**Priority**: P2 (Medium)  
**Effort**: Medium (1-2 days)  
**Dependencies**: None  
**Can Parallelize**: Yes

#### Success Criteria

- [x] Shows all pipeline stages with status icons
- [x] Current stage highlighted/animated
- [x] Per-stage and overall progress bars
- [x] Duration tracking per stage
- [x] Responsive to window resizing

### 3.3 Findings Table Widget (`ui/widgets/findings_table.py`)

**Priority**: P2 (Medium)  
**Effort**: Medium (1-2 days)  
**Dependencies**: None  
**Can Parallelize**: Yes

#### Success Criteria

- [x] Severity-based row coloring
- [x] Sortable by any column (keyboard shortcut)
- [x] Filterable by severity, type, host
- [x] Real-time updates when new findings arrive
- [x] Export selection to JSON
- [x] Enter key opens finding detail view

---

## Wave 4: Ecosystem & Extensibility

**Timeline**: 3-4 weeks  
**Goal**: Enable community contributions and integrations

### 4.1 Webhook Notifications

**Priority**: P3 (Medium)  
**Effort**: Medium (2-3 days)  
**Dependencies**: None  
**Blocks**: None

#### Technical Approach

**Design**: Queue-based async with exponential backoff retry

**Events Supported**:
- `scan_started` - Scan begins
- `scan_completed` - Scan finishes successfully
- `scan_failed` - Scan errors out
- `finding_discovered` - New finding (configurable severity threshold)
- `stage_completed` - Pipeline stage done

#### Success Criteria

- [x] Slack notifications with proper formatting (attachments, colors)
- [x] Discord notifications with embeds
- [x] Rate limiting prevents API abuse
- [x] Retry logic handles transient failures
- [x] Configurable event filtering
- [x] Configurable severity threshold
- [x] Tests mock HTTP calls

### 4.2 Plugin System (Tool Adapters Only)

**Priority**: P3 (High value)  
**Effort**: Large (4-6 days)  
**Dependencies**: Stable ToolAdapter interface  
**Blocks**: Community contributions

#### Scope Decision

**V1 Scope**: Tool Adapters Only
- Community can add new security tools
- Well-defined, safe scope
- Clear interface contract

**Future (V2+)**: Pipeline hooks, finding enrichment, custom reports

#### Discovery Methods

1. **Entry Points**: `galehuntui.plugins.tools` (installed via pip)
2. **Directory Scanning**: `~/.local/share/galehuntui/plugins/`
3. **Manual Registration**: Programmatic

#### Success Criteria

- [x] Plugins discovered from entry points
- [x] Plugins discovered from user plugin directory
- [x] Plugin validation before loading (environment check)
- [x] `galehuntui plugins list` shows installed plugins
- [x] `galehuntui plugins enable/disable <name>` works
- [x] Failed plugins don't crash the application
- [x] Documentation for creating plugins
- [x] Example plugin repository/template

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration breaks existing databases | Medium | High | Backup before migrate; rollback support; extensive testing |
| Plugin security vulnerabilities | Low | High | Environment validation; no code execution hooks in V1 |
| Webhook rate limiting by providers | Medium | Low | Exponential backoff; queue-based delivery |
| Resume state corruption | Low | High | Atomic database writes; checksums; transaction safety |
| TUI performance with large logs | Medium | Medium | Virtual scrolling; log rotation; filtering |

---

## Success Metrics

| Wave | Metric | Target |
|------|--------|--------|
| Wave 0 | Tool installation success rate | 100% |
| Wave 1 | Dependency installation success rate | 100% |
| Wave 2 | Resume success after simulated crash | 100% |
| Wave 3 | User satisfaction with TUI (feedback) | Positive |
| Wave 4 | Community plugins created | 3+ within 6 months |

---

## Appendix: File Changes Summary

### New Files

```
src/galehuntui/
├── tools/
│   ├── registry.yaml                    # Wave 0
│   └── deps/
│       ├── registry.yaml                # Wave 1
│       ├── manager.py                   # Wave 1
│       ├── wordlists.py                 # Wave 1
│       └── templates.py                 # Wave 1
├── storage/
│   └── migrations/
│       ├── __init__.py                  # Wave 2
│       ├── runner.py                    # Wave 2
│       ├── m001_initial_schema.py       # Wave 2
│       └── m002_add_steps_table.py      # Wave 2
├── ui/
│   └── widgets/
│       ├── __init__.py                  # Wave 3
│       ├── log_view.py                  # Wave 3
│       ├── progress.py                  # Wave 3
│       └── findings_table.py            # Wave 3
├── notifications/
│   ├── __init__.py                      # Wave 4
│   ├── webhook.py                       # Wave 4
│   └── providers/
│       ├── __init__.py                  # Wave 4
│       ├── slack.py                     # Wave 4
│       └── discord.py                   # Wave 4
└── plugins/
    ├── __init__.py                      # Wave 4
    ├── manager.py                       # Wave 4
    └── base.py                          # Wave 4
```

### Modified Files

```
src/galehuntui/
├── core/
│   └── exceptions.py                    # Wave 1: Add DependencyError
├── storage/
│   └── database.py                      # Wave 2: Add save_step(), get_steps()
├── orchestrator/
│   ├── state.py                         # Wave 2: Add resume(), persistence
│   └── pipeline.py                      # Wave 2: Add resume_id parameter
├── cli.py                               # Wave 2: Add --resume flag
└── ui/
    └── screens/
        ├── home.py                      # Wave 2: Resume button
        └── run_detail.py                # Wave 3: Use new widgets
```

---

*Last updated: 2026-02-03*
