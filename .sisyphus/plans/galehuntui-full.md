# GaleHunTUI - Full Implementation Work Plan

## TL;DR

> **Quick Summary**: Build GaleHunTUI, a terminal-based automated web pentesting application with Textual TUI, Typer CLI, and integration with 11 security tools. Bottom-up implementation starting from core models through to full TUI.
> 
> **Deliverables**:
> - Complete Python package with CLI (`galehuntui`) and TUI mode
> - 11 tool adapters (subfinder, dnsx, httpx, katana, gau, nuclei, dalfox, ffuf, sqlmap, hydra, wfuzz)
> - 11 TUI screens (Home, New Run, Run Detail, Finding Detail, Tools Manager, Deps Manager, Settings, Profiles, Scope, Help, Setup Wizard)
> - Docker + Local runner with automatic fallback
> - HTML and JSON report generation
> - SQLite database for persistence
> 
> **Estimated Effort**: XL (6-8 weeks)
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: Core → Runners → Tool Adapters → Orchestrator → Storage → TUI → CLI

---

## Context

### Original Request
Build GaleHunTUI berdasarkan spesifikasi lengkap di IDEA.md - aplikasi TUI untuk automated web pentesting yang mendukung bug bounty hunting hingga full blackbox penetration testing.

### Interview Summary
**Key Discussions**:
- **Delivery**: Full implementation (bukan MVP minimal)
- **Testing**: Tests-after strategy
- **Runner**: Docker preferred dengan local fallback
- **Implementation**: Bottom-up approach (core dulu)
- **First tool**: nuclei sebagai reference implementation
- **Config location**: ./configs/ (project root)
- **Concurrent scans**: Single + queue (satu jalan, lainnya antri)
- **Scan-TUI coupling**: Detached (scan terus jalan jika TUI ditutup)
- **Scope**: Optional (tidak wajib define)
- **Tool location**: Project-local (./tools/bin/)
- **Deployment**: Local install (pip install -e .)

**Research Findings**:
- Textual: Screen navigation via push/pop, @work decorator untuk async
- ProjectDiscovery tools: Semua support JSON output, install via GitHub Releases API
- Typer: Command groups via add_typer(), native Rich integration

### Metis Review
**Identified Gaps** (addressed):
- Concurrent scan handling → Single + queue design
- TUI crash behavior → Detached process model
- Empty scope behavior → Optional (default ke target domain)
- Tool installation location → Project-local ./tools/
- Database contention → SQLite WAL mode + retry logic

---

## Work Objectives

### Core Objective
Build a production-ready terminal-based web pentesting orchestrator that automates reconnaissance through vulnerability scanning with reproducible, evidence-backed findings.

### Concrete Deliverables
1. Python package `galehuntui` installable via pip
2. CLI commands: `galehuntui tui`, `galehuntui run`, `galehuntui tools`, `galehuntui deps`, `galehuntui runs`, `galehuntui export`
3. 11 TUI screens dengan full keyboard navigation
4. 11 tool adapters dengan JSON parsing
5. Pipeline orchestrator dengan async execution
6. SQLite database dengan artifact storage
7. HTML dan JSON report generator

### Definition of Done
- [x] `pip install -e .` succeeds without errors
- [x] `galehuntui --version` outputs semantic version
- [x] `galehuntui tools install --all` downloads all 8 required tools
- [x] `galehuntui tui` launches Textual interface
- [x] `galehuntui run --target example.com --profile quick` completes scan
- [x] All 11 TUI screens navigable via keyboard
- [x] HTML report generated in `~/.local/share/galehuntui/runs/<id>/reports/`

### Must Have
- Semua 11 tool adapters functional
- Docker runner dengan local fallback
- 3 engagement modes (bugbounty, authorized, aggressive)
- URL classification (xss, sqli, redirect, ssrf, generic)
- Evidence storage untuk setiap finding
- Detached scan process (survive TUI exit)

### Must NOT Have (Guardrails)
- Resume-able runs (future phase)
- Plugin/extension system (future phase)
- AI/ML-based analysis (future phase)
- Web UI (TUI and CLI only)
- Real-time collaboration features
- Notification systems (email, Slack, webhooks)
- Scheduling/cron functionality
- Export formats beyond HTML and JSON
- ORM (use raw SQL with sqlite3)
- Message queues or caching layers

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO (will be created)
- **User wants tests**: YES (Tests-after)
- **Framework**: pytest + pytest-asyncio

### Automated Verification Approach

Each TODO includes EXECUTABLE verification procedures:

| Deliverable Type | Verification Tool | Method |
|------------------|-------------------|--------|
| Python modules | pytest | Unit tests for critical paths |
| CLI commands | Bash + assert | Exit codes and output validation |
| Tool adapters | Python script | Parse sample output |
| TUI screens | Textual Pilot | Automated screen tests |
| Database | sqlite3 CLI | Schema and data validation |

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately):
├── Task 1: Project setup (pyproject.toml, structure)
├── Task 2: Core models (Finding, ToolResult, ToolConfig)
└── Task 3: Exception hierarchy

Wave 2 (After Wave 1):
├── Task 4: Configuration loader
├── Task 5: Constants and enums
└── Task 6: Tool adapter base class

Wave 3 (After Wave 2):
├── Task 7: Docker runner
├── Task 8: Local runner
├── Task 9: Tool installer (GitHub releases)
└── Task 10: nuclei adapter (reference)

Wave 4 (After Wave 3):
├── Task 11-18: Remaining tool adapters (parallel)
├── Task 19: URL classifier
├── Task 20: Pipeline orchestrator
└── Task 21: Storage layer (SQLite + artifacts)

Wave 5 (After Wave 4):
├── Task 22-32: TUI screens (can parallelize some)
├── Task 33: CLI commands
├── Task 34: Report generator
└── Task 35: Integration testing
```

### Dependency Matrix

| Task | Depends On | Blocks | Parallel With |
|------|------------|--------|---------------|
| 1 (setup) | None | 2, 3, 4, 5, 6 | - |
| 2 (models) | 1 | 7, 8, 10-18, 20, 21 | 3, 4, 5 |
| 3 (exceptions) | 1 | 7, 8, 10-18 | 2, 4, 5 |
| 6 (adapter base) | 2, 3, 4 | 10-18 | - |
| 10 (nuclei) | 6, 7, 8 | 11-18 (pattern) | - |
| 11-18 (adapters) | 10 | 20 | Each other |
| 20 (orchestrator) | 11-18, 19, 21 | 22-32 | - |
| 22-32 (TUI) | 20 | 33 | Some screens |

---

## TODOs

### Phase 1: Foundation (Week 1)

---

- [x] 1. Project Setup and Structure

  **What to do**:
  - Create pyproject.toml dengan semua dependencies
  - Setup src/galehuntui/ directory structure sesuai AGENTS.md
  - Create __init__.py files
  - Setup .gitignore untuk tools/, *.pyc, __pycache__, .venv/
  - Create empty configs/ directory dengan example files

  **Must NOT do**:
  - Add unnecessary dependencies
  - Create complex build system

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
    - Simple file creation task

  **Parallelization**:
  - **Can Run In Parallel**: NO (foundation task)
  - **Parallel Group**: Wave 1 (solo start)
  - **Blocks**: Tasks 2-6
  - **Blocked By**: None

  **References**:
  - `IDEA.md:2123-2128` - pyproject.toml dependencies
  - `AGENTS.md` - Directory structure specification

  **Acceptance Criteria**:
  ```bash
  # Directory structure exists
  ls src/galehuntui/core/ src/galehuntui/orchestrator/ src/galehuntui/runner/ src/galehuntui/tools/ src/galehuntui/classifier/ src/galehuntui/reporting/ src/galehuntui/storage/ src/galehuntui/ui/
  # Assert: Exit code 0
  
  # pyproject.toml is valid
  python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))"
  # Assert: Exit code 0
  
  # Package installable
  pip install -e . && python -c "import galehuntui"
  # Assert: Exit code 0
  ```

  **Commit**: YES
  - Message: `feat(core): initialize project structure and pyproject.toml`
  - Files: `pyproject.toml`, `src/galehuntui/**/__init__.py`, `.gitignore`

---

- [x] 2. Core Data Models

  **What to do**:
  - Implement `Finding` dataclass dengan semua fields dari IDEA.md
  - Implement `Severity` dan `Confidence` enums
  - Implement `ToolResult` dataclass
  - Implement `ToolConfig` dataclass
  - Implement `RunState`, `RunConfig`, `ScanProfile` models
  - Use Pydantic untuk validation where needed

  **Must NOT do**:
  - Over-engineer dengan inheritance hierarchies
  - Add ORM mappings (raw dataclasses only)

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []
    - Standard Python dataclass implementation

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with 3, 4, 5)
  - **Blocks**: Tasks 6, 7, 8, 10-21
  - **Blocked By**: Task 1

  **References**:
  - `IDEA.md:807-845` - Finding schema definition
  - `AGENTS.md` - Core data models section
  - `IDEA.md:267-295` - ToolResult and ToolConfig

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.core.models import Finding, Severity, Confidence, ToolResult, ToolConfig
  from datetime import datetime
  
  # Test Finding creation
  f = Finding(
      id='test-123',
      run_id='run-456',
      type='xss',
      severity=Severity.HIGH,
      confidence=Confidence.CONFIRMED,
      host='example.com',
      url='https://example.com/search?q=test',
      parameter='q',
      evidence_paths=['/path/to/evidence'],
      tool='dalfox',
      timestamp=datetime.now(),
      title='Reflected XSS',
      description='XSS in search parameter',
      reproduction_steps=['Step 1', 'Step 2'],
      remediation='Encode output',
      references=['https://owasp.org/xss']
  )
  assert f.severity == Severity.HIGH
  
  # Test ToolResult
  tr = ToolResult(stdout='output', stderr='', exit_code=0, duration=1.5, output_path=None)
  assert tr.success == True
  
  print('PASS')
  "
  # Assert: Output contains "PASS"
  ```

  **Commit**: YES
  - Message: `feat(core): implement Finding, ToolResult, and ToolConfig models`
  - Files: `src/galehuntui/core/models.py`

---

- [x] 3. Exception Hierarchy

  **What to do**:
  - Implement `GaleHunTUIError` base exception
  - Implement config exceptions: `ConfigError`, `InvalidScopeError`, `ProfileNotFoundError`
  - Implement tool exceptions: `ToolError`, `ToolNotFoundError`, `ToolInstallError`, `ToolTimeoutError`, `ToolExecutionError`
  - Implement pipeline exceptions: `PipelineError`, `ScopeViolationError`, `RateLimitExceededError`
  - Implement storage exceptions: `StorageError`, `ArtifactNotFoundError`

  **Must NOT do**:
  - Create too granular exceptions
  - Add exception handling logic here (just definitions)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
    - Simple class definitions

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with 2, 4, 5)
  - **Blocks**: Tasks 6, 7, 8, 10-18
  - **Blocked By**: Task 1

  **References**:
  - `AGENTS.md` - Exception Hierarchy section

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.core.exceptions import (
      GaleHunTUIError,
      ConfigError, InvalidScopeError, ProfileNotFoundError,
      ToolError, ToolNotFoundError, ToolInstallError, ToolTimeoutError, ToolExecutionError,
      PipelineError, ScopeViolationError, RateLimitExceededError,
      StorageError, ArtifactNotFoundError
  )
  
  # Verify inheritance
  assert issubclass(ConfigError, GaleHunTUIError)
  assert issubclass(ToolNotFoundError, ToolError)
  assert issubclass(ToolError, GaleHunTUIError)
  
  # Test raising
  try:
      raise ToolTimeoutError('nuclei timed out after 300s')
  except GaleHunTUIError as e:
      assert 'nuclei' in str(e)
  
  print('PASS')
  "
  # Assert: Output contains "PASS"
  ```

  **Commit**: YES
  - Message: `feat(core): implement exception hierarchy`
  - Files: `src/galehuntui/core/exceptions.py`

---

- [x] 4. Configuration Loader

  **What to do**:
  - Implement YAML configuration loader dengan PyYAML
  - Support loading dari ./configs/ (project root)
  - Implement `Config` class dengan Pydantic validation
  - Support scope configuration (allowlist, denylist, exclusions)
  - Support profile configuration (quick, standard, deep)
  - Support mode configuration (bugbounty, authorized, aggressive)
  - Implement rate limit settings per mode

  **Must NOT do**:
  - Support multiple config formats (YAML only)
  - Implement config GUI editor
  - Add environment variable overrides (keep simple)

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with 2, 3, 5)
  - **Blocks**: Tasks 6, 7, 8, 20
  - **Blocked By**: Task 1

  **References**:
  - `IDEA.md:148-171` - Scope configuration format
  - `IDEA.md:184-215` - Scan profiles format
  - `IDEA.md:1684-1759` - Mode definitions
  - `AGENTS.md` - Configuration Files section

  **Acceptance Criteria**:
  ```bash
  # Create test config
  mkdir -p configs
  cat > configs/test_scope.yaml << 'EOF'
  target:
    domain: example.com
  scope:
    allowlist:
      - "*.example.com"
    denylist:
      - "admin.example.com"
    exclusions:
      paths:
        - "/logout"
      extensions:
        - ".pdf"
  EOF
  
  python -c "
  from galehuntui.core.config import load_scope_config
  from pathlib import Path
  
  scope = load_scope_config(Path('configs/test_scope.yaml'))
  assert scope.target.domain == 'example.com'
  assert '*.example.com' in scope.scope.allowlist
  assert 'admin.example.com' in scope.scope.denylist
  print('PASS')
  "
  # Assert: Output contains "PASS"
  ```

  **Commit**: YES
  - Message: `feat(core): implement YAML configuration loader`
  - Files: `src/galehuntui/core/config.py`, `configs/scope.example.yaml`, `configs/profiles.yaml`, `configs/modes.yaml`

---

- [x] 5. Constants and Enums

  **What to do**:
  - Implement `EngagementMode` enum (bugbounty, authorized, aggressive)
  - Implement `PipelineStage` enum
  - Implement `ClassificationGroup` enum (xss_candidates, sqli_candidates, etc.)
  - Define `STATIC_EXTENSIONS` set
  - Define rate limit constants per mode
  - Define default timeouts and concurrency limits

  **Must NOT do**:
  - Hardcode values that should be configurable

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with 2, 3, 4)
  - **Blocks**: Tasks 6, 19, 20
  - **Blocked By**: Task 1

  **References**:
  - `IDEA.md:786-798` - STATIC_EXTENSIONS
  - `IDEA.md:1667-1676` - Mode comparison table
  - `AGENTS.md` - URL Classification section

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.core.constants import (
      EngagementMode, PipelineStage, ClassificationGroup,
      STATIC_EXTENSIONS, RATE_LIMITS
  )
  
  assert EngagementMode.BUGBOUNTY.value == 'bugbounty'
  assert '.png' in STATIC_EXTENSIONS
  assert '.pdf' in STATIC_EXTENSIONS
  assert RATE_LIMITS[EngagementMode.BUGBOUNTY]['global'] == 30
  print('PASS')
  "
  # Assert: Output contains "PASS"
  ```

  **Commit**: YES
  - Message: `feat(core): implement constants and enums`
  - Files: `src/galehuntui/core/constants.py`

---

### Phase 2: Tool Infrastructure (Week 2)

---

- [x] 6. Tool Adapter Base Class

  **What to do**:
  - Implement abstract `ToolAdapter` class dengan ABC
  - Define abstract methods: `run()`, `stream()`, `parse_output()`, `build_command()`, `check_available()`, `get_version()`
  - Implement common helper methods
  - Add type hints untuk semua methods
  - Support both sync and async execution patterns

  **Must NOT do**:
  - Implement retry logic (orchestrator's job)
  - Add caching layer
  - Over-complicate with too many abstract methods

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (after core)
  - **Blocks**: Tasks 10-18
  - **Blocked By**: Tasks 2, 3, 4

  **References**:
  - `AGENTS.md` - Tool Adapter Contract section
  - `IDEA.md:267-295` - Adapter contract from spec

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.tools.base import ToolAdapter
  from abc import ABC
  import inspect
  
  # Verify it's abstract
  assert issubclass(ToolAdapter, ABC)
  
  # Verify abstract methods exist
  assert hasattr(ToolAdapter, 'run')
  assert hasattr(ToolAdapter, 'stream')
  assert hasattr(ToolAdapter, 'parse_output')
  assert hasattr(ToolAdapter, 'build_command')
  assert hasattr(ToolAdapter, 'check_available')
  assert hasattr(ToolAdapter, 'get_version')
  
  # Verify type hints
  sig = inspect.signature(ToolAdapter.run)
  assert 'inputs' in sig.parameters
  assert 'config' in sig.parameters
  
  print('PASS')
  "
  # Assert: Output contains "PASS"
  ```

  **Commit**: YES
  - Message: `feat(tools): implement ToolAdapter abstract base class`
  - Files: `src/galehuntui/tools/base.py`

---

- [x] 7. Docker Runner

  **What to do**:
  - Implement `DockerRunner` class
  - Detect Docker availability (`docker info`)
  - Build container execution commands
  - Handle volume mounts for input/output
  - Implement timeout handling dengan container stop
  - Stream stdout/stderr dari container

  **Must NOT do**:
  - Build custom Docker images (use official tool images)
  - Implement Docker Compose orchestration

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with 8, 9)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 2, 3

  **References**:
  - `IDEA.md:99-109` - Runner selection strategy

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.runner.docker import DockerRunner
  import asyncio
  
  runner = DockerRunner()
  
  # Check if Docker is available (may fail on systems without Docker)
  available = asyncio.run(runner.is_available())
  print(f'Docker available: {available}')
  
  # Test command building
  cmd = runner.build_command(
      image='projectdiscovery/httpx:latest',
      args=['-u', 'https://example.com', '-json'],
      volumes={'/tmp/input': '/input', '/tmp/output': '/output'}
  )
  assert 'docker' in cmd[0]
  assert 'run' in cmd
  print('PASS')
  "
  # Assert: Output contains "PASS"
  ```

  **Commit**: YES
  - Message: `feat(runner): implement Docker runner with container management`
  - Files: `src/galehuntui/runner/docker.py`, `src/galehuntui/runner/base.py`

---

- [x] 8. Local Runner

  **What to do**:
  - Implement `LocalRunner` class as fallback
  - Use `asyncio.create_subprocess_exec()` for execution
  - Implement timeout dengan SIGTERM → SIGKILL escalation
  - Handle stdin/stdout/stderr streaming
  - Check binary availability sebelum execution

  **Must NOT do**:
  - Use blocking subprocess calls
  - Ignore timeout handling

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with 7, 9)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 2, 3

  **References**:
  - `AGENTS.md` - Async Patterns section
  - Research findings on asyncio subprocess handling

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.runner.local import LocalRunner
  from pathlib import Path
  import asyncio
  
  runner = LocalRunner()
  
  # Test with simple command
  result = asyncio.run(runner.execute(
      command=['echo', 'hello'],
      timeout=10
  ))
  
  assert result.exit_code == 0
  assert 'hello' in result.stdout
  print('PASS')
  "
  # Assert: Output contains "PASS"
  ```

  **Commit**: YES
  - Message: `feat(runner): implement local runner with async subprocess`
  - Files: `src/galehuntui/runner/local.py`

---

- [x] 9. Tool Installer

  **What to do**:
  - Implement `ToolInstaller` class
  - Download binaries from GitHub Releases API
  - Detect platform (linux-amd64, linux-arm64)
  - Extract zip/tar.gz archives
  - Set executable permissions
  - Compute and verify checksums
  - Store installed versions in tools/versions.json
  - Support registry.yaml untuk tool definitions

  **Must NOT do**:
  - Install to system paths (project-local only)
  - Implement auto-update on every run

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 3 (with 7, 8)
  - **Blocks**: Task 10
  - **Blocked By**: Tasks 2, 3, 4

  **References**:
  - `IDEA.md:544-645` - Tool installer implementation
  - `IDEA.md:367-466` - Tool registry YAML format
  - Research findings on GitHub Releases API

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.tools.installer import ToolInstaller
  from pathlib import Path
  import asyncio
  
  installer = ToolInstaller(tools_dir=Path('./tools'))
  
  # Test platform detection
  platform = installer.detect_platform()
  assert platform in ['linux-amd64', 'linux-arm64']
  
  # Test GitHub API (just fetch, don't download)
  release = asyncio.run(installer.get_latest_release('projectdiscovery/httpx'))
  assert 'tag_name' in release
  print(f'Latest httpx: {release[\"tag_name\"]}')
  print('PASS')
  "
  # Assert: Output contains "PASS"
  ```

  **Commit**: YES
  - Message: `feat(tools): implement GitHub releases-based tool installer`
  - Files: `src/galehuntui/tools/installer.py`, `tools/registry.yaml`

---

- [x] 10. Nuclei Adapter (Reference Implementation)

  **What to do**:
  - Implement `NucleiAdapter` extending `ToolAdapter`
  - Build command dengan proper flags (-json, -silent, -rate-limit, -severity)
  - Parse JSONL output ke `Finding` objects
  - Map nuclei severity ke internal `Severity` enum
  - Handle template path configuration
  - Support mode-specific settings (rate limits, templates)

  **Must NOT do**:
  - Implement all edge cases (this is reference for other adapters)
  - Add nuclei-specific caching

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (reference implementation)
  - **Parallel Group**: Wave 3 (after runners)
  - **Blocks**: Tasks 11-18 (pattern to follow)
  - **Blocked By**: Tasks 6, 7, 8, 9

  **References**:
  - `AGENTS.md` - Adapter Implementation Example (httpx)
  - Research findings on nuclei JSON output format
  - `IDEA.md:253-264` - Integrated tools table

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.tools.adapters.nuclei import NucleiAdapter
  from galehuntui.core.models import Finding, Severity
  from pathlib import Path
  import json
  
  adapter = NucleiAdapter(bin_path=Path('./tools/bin'))
  
  # Test command building
  cmd = adapter.build_command(
      inputs=['https://example.com'],
      config={'timeout': 300, 'rate_limit': 100, 'severity': 'critical,high'}
  )
  assert 'nuclei' in str(cmd)
  assert '-json' in cmd
  assert '-silent' in cmd
  
  # Test output parsing
  sample_output = json.dumps({
      'template-id': 'CVE-2021-26855',
      'info': {'severity': 'critical', 'name': 'Exchange SSRF'},
      'host': 'https://example.com',
      'matched-at': 'https://example.com/owa'
  })
  findings = adapter.parse_output(sample_output)
  assert len(findings) == 1
  assert findings[0].severity == Severity.CRITICAL
  
  print('PASS')
  "
  # Assert: Output contains "PASS"
  ```

  **Commit**: YES
  - Message: `feat(tools): implement nuclei adapter as reference implementation`
  - Files: `src/galehuntui/tools/adapters/nuclei.py`, `src/galehuntui/tools/adapters/__init__.py`

---

### Phase 3: Remaining Tool Adapters (Week 2-3)

---

- [x] 11. Subfinder Adapter

  **What to do**:
  - Implement `SubfinderAdapter` following nuclei pattern
  - Handle domain input
  - Parse JSON output (host, source, timestamp)
  - No rate limiting needed (passive sources)

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4 (with 12-18)
  - **Blocks**: Task 20
  - **Blocked By**: Task 10

  **References**:
  - Task 10 (nuclei adapter) as pattern
  - Research findings on subfinder JSON format

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.tools.adapters.subfinder import SubfinderAdapter
  from pathlib import Path
  import json
  
  adapter = SubfinderAdapter(bin_path=Path('./tools/bin'))
  
  # Test output parsing
  sample = json.dumps({'host': 'api.example.com', 'source': 'crtsh'})
  results = adapter.parse_output(sample)
  assert len(results) == 1
  assert results[0]['host'] == 'api.example.com'
  print('PASS')
  "
  ```

  **Commit**: YES (group dengan 12-18)
  - Message: `feat(tools): implement reconnaissance tool adapters`

---

- [x] 12. DNSX Adapter

  **What to do**:
  - Implement `DnsxAdapter`
  - Handle host list input
  - Parse JSON output dengan resolved IPs

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 20
  - **Blocked By**: Task 10

  **Commit**: YES (group)

---

- [x] 13. HTTPX Adapter

  **What to do**:
  - Implement `HttpxAdapter`
  - Handle host list input via stdin
  - Parse JSON output (url, status_code, title, technologies)
  - Configure rate limiting

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 20
  - **Blocked By**: Task 10

  **Commit**: YES (group)

---

- [x] 14. Katana Adapter

  **What to do**:
  - Implement `KatanaAdapter`
  - Handle URL input untuk crawling
  - Parse JSON output
  - Configure depth dan scope

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 20
  - **Blocked By**: Task 10

  **Commit**: YES (group)

---

- [x] 15. GAU Adapter

  **What to do**:
  - Implement `GauAdapter`
  - Handle domain input
  - Parse plain text output (one URL per line)
  - Convert to JSON-like structure

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 20
  - **Blocked By**: Task 10

  **Commit**: YES (group)

---

- [x] 16. Dalfox Adapter

  **What to do**:
  - Implement `DalfoxAdapter`
  - Handle URL input dengan parameters
  - Parse JSON output ke Finding dengan XSS type
  - Configure mode-specific options

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 20
  - **Blocked By**: Task 10

  **Commit**: YES (group)

---

- [x] 17. FFUF Adapter

  **What to do**:
  - Implement `FfufAdapter`
  - Handle URL dengan FUZZ keyword
  - Parse JSON output
  - Configure wordlist path dan rate limiting

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 20
  - **Blocked By**: Task 10

  **Commit**: YES (group)

---

- [x] 18. SQLMap, Hydra, Wfuzz Adapters (Optional Tools)

  **What to do**:
  - Implement `SqlmapAdapter` dengan mode restrictions
  - Implement `HydraAdapter` dengan mode restrictions
  - Implement `WfuzzAdapter` dengan mode restrictions
  - These only available in authorized/aggressive modes

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 20
  - **Blocked By**: Task 10

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.tools.adapters.sqlmap import SqlmapAdapter
  from galehuntui.core.constants import EngagementMode
  
  adapter = SqlmapAdapter(bin_path=None)
  assert adapter.mode_required == EngagementMode.AUTHORIZED
  print('PASS')
  "
  ```

  **Commit**: YES
  - Message: `feat(tools): implement optional tool adapters (sqlmap, hydra, wfuzz)`

---

### Phase 4: Data Processing & Orchestration (Week 3-4)

---

- [x] 19. URL Classifier

  **What to do**:
  - Implement `URLClassifier` class
  - Implement `URLNormalizer` untuk URL cleaning
  - Implement `URLDeduper` untuk deduplication
  - Classification groups: xss_candidates, sqli_candidates, redirect_candidates, ssrf_candidates, generic
  - Filter static extensions
  - Support regex pattern matching

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 20
  - **Blocked By**: Tasks 2, 5

  **References**:
  - `IDEA.md:766-798` - Classification pipeline and groups
  - `AGENTS.md` - URL Classification section

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.classifier import URLClassifier
  
  classifier = URLClassifier()
  urls = [
      'https://example.com/search?q=test',
      'https://example.com/user?id=123',
      'https://example.com/redirect?url=https://evil.com',
      'https://example.com/image.png'
  ]
  results = classifier.classify(urls)
  
  assert 'https://example.com/search?q=test' in results.xss_candidates
  assert 'https://example.com/user?id=123' in results.sqli_candidates
  assert 'https://example.com/redirect?url=https://evil.com' in results.redirect_candidates
  assert 'https://example.com/image.png' not in results.all_candidates
  print('PASS')
  "
  ```

  **Commit**: YES
  - Message: `feat(classifier): implement URL normalization, deduplication, and classification`
  - Files: `src/galehuntui/classifier/normalizer.py`, `src/galehuntui/classifier/deduper.py`, `src/galehuntui/classifier/classifier.py`

---

- [x] 20. Pipeline Orchestrator

  **What to do**:
  - Implement `PipelineOrchestrator` class
  - Define pipeline stages (subfinder → dnsx → httpx → katana/gau → classify → nuclei → injection tools)
  - Implement async worker pool dengan asyncio
  - Handle stage dependencies dan data flow
  - Implement run state management
  - Support single scan + queue (block concurrent)
  - Implement detached process model (survive TUI exit)
  - Apply rate limiting per mode

  **Recommended Agent Profile**:
  - **Category**: `ultrabrain`
  - **Skills**: []
    - Complex async coordination logic

  **Parallelization**:
  - **Can Run In Parallel**: NO (complex, needs focus)
  - **Parallel Group**: Wave 4 (after adapters)
  - **Blocks**: Tasks 22-32, 33
  - **Blocked By**: Tasks 11-19, 21

  **References**:
  - `IDEA.md:115-139` - Pipeline stages
  - `IDEA.md:223-246` - Worker pool architecture
  - `AGENTS.md` - Pipeline Stages section

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.orchestrator.pipeline import PipelineOrchestrator
  from galehuntui.core.constants import EngagementMode
  import asyncio
  
  orchestrator = PipelineOrchestrator(
      mode=EngagementMode.BUGBOUNTY,
      profile='quick'
  )
  
  # Verify stages are defined
  assert len(orchestrator.stages) > 0
  assert 'subfinder' in [s.tool for s in orchestrator.stages]
  
  # Verify rate limits applied
  assert orchestrator.rate_limit <= 30  # bugbounty mode
  
  print('PASS')
  "
  ```

  **Commit**: YES
  - Message: `feat(orchestrator): implement async pipeline with worker pool and rate limiting`
  - Files: `src/galehuntui/orchestrator/pipeline.py`, `src/galehuntui/orchestrator/scheduler.py`, `src/galehuntui/orchestrator/state.py`

---

- [x] 21. Storage Layer (SQLite + Artifacts)

  **What to do**:
  - Implement SQLite database dengan WAL mode
  - Create tables: runs, findings, artifacts
  - Implement `RunRepository`, `FindingRepository`
  - Implement `ArtifactStorage` untuk file management
  - Store evidence files (requests, responses, screenshots)
  - Handle concurrent access dengan retry logic

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 20, 22-32
  - **Blocked By**: Tasks 2, 3

  **References**:
  - `IDEA.md:2130-2154` - Data storage layout
  - `AGENTS.md` - Storage Layout section

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.storage.database import Database
  from galehuntui.storage.artifacts import ArtifactStorage
  from pathlib import Path
  import tempfile
  
  with tempfile.TemporaryDirectory() as tmpdir:
      db = Database(Path(tmpdir) / 'test.db')
      db.initialize()
      
      # Check WAL mode
      result = db.execute('PRAGMA journal_mode;')
      assert result[0][0].lower() == 'wal'
      
      # Check tables exist
      tables = db.execute(\"SELECT name FROM sqlite_master WHERE type='table'\")
      table_names = [t[0] for t in tables]
      assert 'runs' in table_names
      assert 'findings' in table_names
      
      print('PASS')
  "
  ```

  **Commit**: YES
  - Message: `feat(storage): implement SQLite database with WAL mode and artifact storage`
  - Files: `src/galehuntui/storage/database.py`, `src/galehuntui/storage/artifacts.py`

---

### Phase 5: TUI Screens (Week 4-6)

---

- [x] 22. TUI Application Shell

  **What to do**:
  - Implement main `GaleHunTUIApp` class extending Textual `App`
  - Setup screen registry
  - Implement global keybindings (?, Esc, Ctrl+Q, Ctrl+S, Ctrl+T, Ctrl+N)
  - Load TCSS stylesheet
  - Handle app lifecycle (startup, shutdown)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: NO (foundation for other screens)
  - **Parallel Group**: Wave 5 (first)
  - **Blocks**: Tasks 23-32
  - **Blocked By**: Task 20, 21

  **References**:
  - `IDEA.md:928-945` - Global keyboard shortcuts
  - Research findings on Textual app structure

  **Acceptance Criteria**:
  ```python
  # Using Textual Pilot for automated testing
  async def test_app_launches():
      from galehuntui.ui.app import GaleHunTUIApp
      app = GaleHunTUIApp()
      async with app.run_test() as pilot:
          assert pilot.app.title == "GaleHunTUI"
          # Press ? for help
          await pilot.press("?")
          assert "Help" in str(pilot.app.screen)
  ```

  **Commit**: YES
  - Message: `feat(ui): implement main TUI application shell with global keybindings`
  - Files: `src/galehuntui/ui/app.py`, `src/galehuntui/ui/styles/main.tcss`

---

- [x] 23. Home Dashboard Screen

  **What to do**:
  - Implement `HomeScreen` dengan stats overview
  - Show recent runs table
  - Quick actions panel (New Run, Quick Scan, Resume)
  - System status (tools, templates, disk)
  - Keybindings: N, Q, T, S, P

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5 (with 24-32)
  - **Blocks**: None
  - **Blocked By**: Task 22

  **References**:
  - `IDEA.md:949-984` - Home dashboard mockup

  **Commit**: YES (group dengan screens lain)

---

- [x] 24. New Run Screen

  **What to do**:
  - Implement `NewRunScreen` dengan form inputs
  - Target domain input dengan autocomplete
  - Profile selection (quick, standard, deep, custom)
  - Scope file selector
  - Engagement mode selection
  - Advanced options (collapsible)
  - Start run action

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **References**:
  - `IDEA.md:989-1055` - New run screen mockup

  **Commit**: YES (group)

---

- [x] 25. Run Detail Screen

  **What to do**:
  - Implement `RunDetailScreen`
  - Pipeline progress visualization
  - Live logs view dengan auto-scroll
  - Findings table (sortable, filterable)
  - Keybindings: C (cancel), P (pause), E (export), O (open folder)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **References**:
  - `IDEA.md:1059-1101` - Run detail mockup

  **Commit**: YES (group)

---

- [x] 26. Finding Detail Screen

  **What to do**:
  - Implement `FindingDetailScreen`
  - Overview panel (type, severity, confidence, URL)
  - Evidence panel (request/response)
  - Reproduction steps
  - Remediation recommendations
  - Navigation: prev/next finding

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **References**:
  - `IDEA.md:1339-1392` - Finding detail mockup

  **Commit**: YES (group)

---

- [x] 27. Tools Manager Screen

  **What to do**:
  - Implement `ToolsManagerScreen`
  - Core tools table (version, status, update available)
  - Optional tools table (mode required)
  - Actions: Update All, Install, Verify

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **References**:
  - `IDEA.md:1105-1150` - Tools manager mockup

  **Commit**: YES (group)

---

- [x] 28. Dependencies Manager Screen

  **What to do**:
  - Implement `DepsManagerScreen`
  - Nuclei templates section
  - Wordlists section
  - DNS resolvers section
  - Update and clean actions

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **References**:
  - `IDEA.md:1154-1199` - Dependencies manager mockup

  **Commit**: YES (group)

---

- [x] 29. Settings Screen

  **What to do**:
  - Implement `SettingsScreen`
  - Category sidebar (General, Engagement, Rate Limit, etc.)
  - Form fields per category
  - Save and reset actions

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **References**:
  - `IDEA.md:1203-1252` - Settings screen mockup

  **Commit**: YES (group)

---

- [x] 30. Profiles Editor Screen

  **What to do**:
  - Implement `ProfilesEditorScreen`
  - Profile list sidebar
  - Pipeline steps configuration
  - Performance settings
  - Clone, delete, test actions

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **References**:
  - `IDEA.md:1255-1293` - Profiles editor mockup

  **Commit**: YES (group)

---

- [x] 31. Scope Editor Screen

  **What to do**:
  - Implement `ScopeEditorScreen`
  - Scope files sidebar
  - Target domain input
  - Allowlist/denylist editing
  - Path exclusions
  - Validate and preview actions

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **References**:
  - `IDEA.md:1297-1335` - Scope editor mockup

  **Commit**: YES (group)

---

- [x] 32. Help Screen and Setup Wizard

  **What to do**:
  - Implement `HelpScreen` dengan keyboard shortcuts reference
  - Implement `SetupWizardScreen` untuk first-run
  - System check step
  - Tool installation step
  - Dependencies step
  - Configuration step

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
  - **Skills**: [`frontend-ui-ux`]

  **References**:
  - `IDEA.md:1396-1624` - Help and setup wizard mockups

  **Commit**: YES
  - Message: `feat(ui): implement all TUI screens`
  - Files: `src/galehuntui/ui/screens/*.py`

---

### Phase 6: CLI & Reporting (Week 6-7)

---

- [x] 33. CLI Commands

  **What to do**:
  - Implement Typer CLI dengan command groups
  - `galehuntui tui` - launch TUI
  - `galehuntui run` - CLI scan
  - `galehuntui tools` - tool management
  - `galehuntui deps` - dependency management
  - `galehuntui runs` - run management
  - `galehuntui export` - report export
  - Rich progress bars untuk CLI operations

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (after TUI)
  - **Blocks**: None
  - **Blocked By**: Task 20, 22

  **References**:
  - `IDEA.md:2266-2281` - Example commands
  - `AGENTS.md` - CLI Commands Reference
  - Research findings on Typer patterns

  **Acceptance Criteria**:
  ```bash
  # Version command works
  galehuntui --version
  # Assert: Exit code 0, outputs version string
  
  # Help shows all commands
  galehuntui --help | grep -E "(tui|run|tools|deps|runs|export)"
  # Assert: Exit code 0
  
  # Tools list works
  galehuntui tools list
  # Assert: Exit code 0
  ```

  **Commit**: YES
  - Message: `feat(cli): implement Typer CLI with all command groups`
  - Files: `src/galehuntui/cli.py`

---

- [x] 34. Report Generator

  **What to do**:
  - Implement `ReportGenerator` class
  - HTML report dengan Jinja2 templates
  - JSON export
  - Executive summary generation
  - Include evidence links
  - Tool transparency section

  **Recommended Agent Profile**:
  - **Category**: `implementation`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 5
  - **Blocks**: None
  - **Blocked By**: Task 21

  **References**:
  - `IDEA.md:853-878` - Report sections
  - `AGENTS.md` - Reporting section

  **Acceptance Criteria**:
  ```bash
  python -c "
  from galehuntui.reporting.generator import ReportGenerator
  from galehuntui.core.models import Finding, Severity, Confidence
  from datetime import datetime
  from pathlib import Path
  import tempfile
  
  generator = ReportGenerator()
  
  findings = [
      Finding(
          id='test-1',
          run_id='run-1',
          type='xss',
          severity=Severity.HIGH,
          confidence=Confidence.CONFIRMED,
          host='example.com',
          url='https://example.com/search?q=test',
          parameter='q',
          evidence_paths=[],
          tool='dalfox',
          timestamp=datetime.now(),
          title='Reflected XSS',
          description='XSS vulnerability',
          reproduction_steps=['Step 1'],
          remediation='Encode output',
          references=[]
      )
  ]
  
  with tempfile.TemporaryDirectory() as tmpdir:
      html_path = generator.generate_html(findings, Path(tmpdir) / 'report.html')
      assert html_path.exists()
      content = html_path.read_text()
      assert 'Reflected XSS' in content
      
      json_path = generator.generate_json(findings, Path(tmpdir) / 'findings.json')
      assert json_path.exists()
      
      print('PASS')
  "
  ```

  **Commit**: YES
  - Message: `feat(reporting): implement HTML and JSON report generators`
  - Files: `src/galehuntui/reporting/generator.py`, `src/galehuntui/reporting/templates/*.j2`, `src/galehuntui/reporting/exporters/*.py`

---

### Phase 7: Testing & Polish (Week 7-8)

---

- [x] 35. Critical Path Tests

  **What to do**:
  - Setup pytest dengan pytest-asyncio
  - Write tests untuk URL classifier
  - Write tests untuk tool adapter parsing
  - Write tests untuk pipeline execution (mocked)
  - Write tests untuk database operations
  - Write integration test untuk full scan flow

  **Recommended Agent Profile**:
  - **Category**: `testing`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 5 (final)
  - **Blocks**: None
  - **Blocked By**: All previous tasks

  **References**:
  - `AGENTS.md` - Testing Guidelines section

  **Acceptance Criteria**:
  ```bash
  # Run tests
  pytest tests/ -v --tb=short
  # Assert: Exit code 0
  
  # Coverage report
  pytest tests/ --cov=galehuntui --cov-report=term-missing
  # Assert: Coverage > 60% untuk critical paths
  ```

  **Commit**: YES
  - Message: `test: add critical path tests for classifier, adapters, and pipeline`
  - Files: `tests/**/*.py`, `tests/conftest.py`

---

## Commit Strategy

| After Task | Message | Verification |
|------------|---------|--------------|
| 1 | `feat(core): initialize project structure` | pip install -e . |
| 2 | `feat(core): implement data models` | python import test |
| 3 | `feat(core): implement exceptions` | python import test |
| 4 | `feat(core): implement config loader` | config parse test |
| 5 | `feat(core): implement constants` | python import test |
| 6 | `feat(tools): implement adapter base` | python import test |
| 7 | `feat(runner): implement docker runner` | runner build command test |
| 8 | `feat(runner): implement local runner` | echo command test |
| 9 | `feat(tools): implement installer` | GitHub API test |
| 10 | `feat(tools): implement nuclei adapter` | parse output test |
| 11-17 | `feat(tools): implement recon adapters` | parse tests |
| 18 | `feat(tools): implement optional adapters` | mode restriction test |
| 19 | `feat(classifier): implement URL classifier` | classification test |
| 20 | `feat(orchestrator): implement pipeline` | stage definition test |
| 21 | `feat(storage): implement database` | WAL mode test |
| 22 | `feat(ui): implement app shell` | Textual launch test |
| 23-32 | `feat(ui): implement all screens` | Pilot tests |
| 33 | `feat(cli): implement commands` | --help test |
| 34 | `feat(reporting): implement generators` | HTML/JSON output test |
| 35 | `test: add critical path tests` | pytest pass |

---

## Success Criteria

### Verification Commands
```bash
# 1. Package installs
pip install -e . && python -c "import galehuntui; print('OK')"

# 2. Version works
galehuntui --version

# 3. Tools can be installed
galehuntui tools install httpx nuclei && galehuntui tools verify

# 4. TUI launches
timeout 5 galehuntui tui || true  # Will timeout, but should start

# 5. CLI scan works (with installed tools)
galehuntui run --target testphp.vulnweb.com --profile quick --mode bugbounty

# 6. Export works
galehuntui export --run-id <latest> --format html --output report.html
```

### Final Checklist
- [x] All 11 tool adapters implemented and tested
- [x] All 11 TUI screens navigable
- [x] All CLI commands functional
- [x] Docker runner works when Docker available
- [x] Local runner works as fallback
- [x] SQLite database persists data correctly
- [x] HTML and JSON reports generated
- [x] Rate limiting enforced per mode
- [x] Evidence stored for all findings
- [x] Critical path tests passing
