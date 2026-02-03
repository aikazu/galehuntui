# AGENTS.md - GaleHunTUI Development Guide

> **For AI Agents**: This document provides comprehensive context for developing GaleHunTUI. Read thoroughly before making changes.

---

## Project Identity

| Attribute | Value |
|-----------|-------|
| **Name** | GaleHunTUI |
| **Type** | Terminal-based Automated Web Pentesting Application |
| **Platform** | Linux (Debian/Arch-based distros) |
| **Language** | Python 3.11+ |
| **TUI Framework** | Textual |
| **CLI Framework** | Typer |
| **Status** | MVP Complete (218 tests passing) |

### Vision Statement

```
Reconnaissance -> Vulnerability Scanning -> Targeted Injection -> Comprehensive Reporting
```

GaleHunTUI orchestrates automated web pentesting workflows through an intuitive terminal interface. It supports bug bounty hunting, authorized pentests, and full blackbox assessments with reproducible, evidence-backed findings.

---

## Architecture Overview

```
+-------------------------------------------------------------------------+
|                              GaleHunTUI                                  |
+-------------------------------------------------------------------------+
|  +-----------+  +-----------+  +-----------+  +-----------+             |
|  |    CLI    |  |    TUI    |  |    API    |  |   Config  |             |
|  |  (Typer)  |  | (Textual) |  |  (Future) |  |  (YAML)   |             |
|  +-----+-----+  +-----+-----+  +-----+-----+  +-----+-----+             |
|        +---------------+---------------+------------+                    |
|                        v                                                 |
|  +------------------------------------------------------------------+   |
|  |                        ORCHESTRATOR                               |   |
|  |   +------------+  +------------+  +------------+                  |   |
|  |   |  Pipeline  |  | Scheduler  |  |   State    |                  |   |
|  |   |  Manager   |  |  (async)   |  |  Manager   |                  |   |
|  |   +------------+  +------------+  +------------+                  |   |
|  +-------------------------------+----------------------------------+   |
|                                  v                                       |
|  +------------------------------------------------------------------+   |
|  |                          RUNNERS                                  |   |
|  |   +------------------+     +------------------+                   |   |
|  |   |  Docker Runner   |     |  Local Runner    |                   |   |
|  |   |   (Preferred)    |     |   (Fallback)     |                   |   |
|  |   +------------------+     +------------------+                   |   |
|  +-------------------------------+----------------------------------+   |
|                                  v                                       |
|  +------------------------------------------------------------------+   |
|  |                       TOOL ADAPTERS                               |   |
|  |  +--------+ +--------+ +--------+ +--------+ +--------+          |   |
|  |  |subfinder| | httpx  | | nuclei | | dalfox | |  ffuf  |  ...    |   |
|  |  +--------+ +--------+ +--------+ +--------+ +--------+          |   |
|  +-------------------------------+----------------------------------+   |
|                                  v                                       |
|  +------------------------------------------------------------------+   |
|  |                      DATA PROCESSING                              |   |
|  |  +------------+  +------------+  +------------+                   |   |
|  |  | Classifier |  | Normalizer |  |  Deduper   |                   |   |
|  |  +------------+  +------------+  +------------+                   |   |
|  +-------------------------------+----------------------------------+   |
|                                  v                                       |
|  +------------------------------------------------------------------+   |
|  |                    STORAGE & REPORTING                            |   |
|  |  +------------+  +------------+  +------------+                   |   |
|  |  |   SQLite   |  | Artifacts  |  |  Reports   |                   |   |
|  |  |  Database  |  |  Storage   |  | Generator  |                   |   |
|  |  +------------+  +------------+  +------------+                   |   |
|  +------------------------------------------------------------------+   |
+-------------------------------------------------------------------------+
```

---

## Implemented Directory Structure

```
galehuntui/
+-- src/galehuntui/           # Main source code
|   +-- __init__.py
|   +-- cli.py                # Typer CLI entry point (IMPLEMENTED)
|   |
|   +-- core/                 # Core infrastructure (IMPLEMENTED)
|   |   +-- __init__.py
|   |   +-- config.py         # Configuration loader (YAML + Pydantic)
|   |   +-- models.py         # Finding, ToolResult, ToolConfig, RunMetadata
|   |   +-- exceptions.py     # Custom exception hierarchy
|   |   +-- constants.py      # Enums (EngagementMode, PipelineStage, etc.)
|   |
|   +-- orchestrator/         # Pipeline coordination (IMPLEMENTED)
|   |   +-- __init__.py
|   |   +-- pipeline.py       # PipelineOrchestrator class
|   |   +-- scheduler.py      # AsyncTaskScheduler
|   |   +-- state.py          # RunStateManager
|   |
|   +-- runner/               # Tool execution layer (IMPLEMENTED)
|   |   +-- __init__.py
|   |   +-- base.py           # Abstract Runner interface
|   |   +-- docker.py         # Docker-based execution
|   |   +-- local.py          # Direct local execution
|   |
|   +-- tools/                # Tool management (IMPLEMENTED)
|   |   +-- __init__.py
|   |   +-- base.py           # ToolAdapter ABC
|   |   +-- installer.py      # GitHub Releases installer
|   |   +-- adapters/         # 11 tool adapters (IMPLEMENTED)
|   |   |   +-- __init__.py
|   |   |   +-- subfinder.py
|   |   |   +-- dnsx.py
|   |   |   +-- httpx.py
|   |   |   +-- katana.py
|   |   |   +-- gau.py
|   |   |   +-- nuclei.py
|   |   |   +-- dalfox.py
|   |   |   +-- ffuf.py
|   |   |   +-- sqlmap.py
|   |   |   +-- wfuzz.py
|   |   +-- deps/             # Dependency managers (IMPLEMENTED)
|   |       +-- __init__.py
|   |       +-- registry.yaml   # Dependency definitions
|   |       +-- manager.py      # DependencyManager class
|   |       +-- wordlists.py    # WordlistManager class
|   |       +-- templates.py    # TemplateManager class
|   |
|   +-- classifier/           # URL processing (IMPLEMENTED)
|   |   +-- __init__.py
|   |   +-- normalizer.py     # URLNormalizer class
|   |   +-- deduper.py        # URLDeduper class
|   |   +-- classifier.py     # URLClassifier class
|   |
|   +-- reporting/            # Report generation (IMPLEMENTED)
|   |   +-- __init__.py
|   |   +-- generator.py      # ReportGenerator class
|   |   +-- templates/        # Jinja2 templates
|   |   |   +-- report.html.j2
|   |   |   +-- finding.html.j2
|   |   +-- exporters/
|   |       +-- __init__.py
|   |       +-- html.py       # HTMLExporter
|   |       +-- json.py       # JSONExporter
|   |
|   +-- storage/              # Data persistence (IMPLEMENTED)
|   |   +-- __init__.py
|   |   +-- database.py       # SQLite with WAL mode
|   |   +-- artifacts.py      # Artifact file management
|   |   +-- migrations/       # Database migrations (IMPLEMENTED)
|   |       +-- __init__.py
|   |       +-- runner.py         # MigrationRunner class
|   |       +-- m001_initial_schema.py
|   |       +-- m002_add_steps_table.py
|   |
|   +-- notifications/        # Webhook notifications (IMPLEMENTED)
|   |   +-- __init__.py
|   |   +-- webhook.py        # WebhookManager class
|   |   +-- providers/
|   |       +-- __init__.py
|   |       +-- base.py       # WebhookProvider ABC
|   |       +-- slack.py      # SlackProvider
|   |       +-- discord.py    # DiscordProvider
|   |
|   +-- plugins/              # Plugin system (IMPLEMENTED)
|   |   +-- __init__.py
|   |   +-- base.py           # ToolPlugin ABC, PluginMetadata
|   |   +-- manager.py        # PluginManager class
|   |
|   +-- ui/                   # Textual TUI (IMPLEMENTED)
|       +-- __init__.py
|       +-- app.py            # GaleHunTUIApp main class
|       +-- screens/          # 11 TUI screens
|       |   +-- __init__.py
|       |   +-- home.py           # Home dashboard
|       |   +-- new_run.py        # New run configuration
|       |   +-- run_detail.py     # Run monitoring
|       |   +-- tools_manager.py  # Tools management
|       |   +-- deps_manager.py   # Dependencies management
|       |   +-- settings.py       # Settings editor
|       |   +-- profiles.py       # Profile editor
|       |   +-- scope.py          # Scope editor
|       |   +-- finding_detail.py # Finding viewer
|       |   +-- help.py           # Help screen
|       |   +-- setup.py          # First-run wizard
|       +-- widgets/          # Custom widgets (IMPLEMENTED)
|       |   +-- __init__.py
|       |   +-- log_view.py       # LogViewWidget class
|       |   +-- progress.py       # PipelineProgressWidget class
|       |   +-- findings_table.py # FindingsTableWidget class
|       +-- styles/
|           +-- __init__.py
|           +-- main.tcss     # Textual CSS
|
+-- tools/                    # External tools (gitignored)
|   +-- bin/                  # Compiled binaries
|
+-- configs/                  # Configuration files (IMPLEMENTED)
|   +-- scope.example.yaml
|   +-- profiles.yaml
|   +-- modes.yaml
|   +-- test_scope.yaml
|
+-- tests/                    # Test suite (218 tests)
|   +-- test_classifier/
|   |   +-- __init__.py
|   |   +-- test_classifier.py   # 40 tests
|   |   +-- test_normalizer.py   # 32 tests
|   +-- test_tools/
|   |   +-- __init__.py
|   |   +-- test_adapters/
|   |       +-- __init__.py
|   |       +-- test_httpx.py    # 21 tests
|   |       +-- test_nuclei.py   # 31 tests
|   |       +-- test_subfinder.py # 26 tests
|   +-- test_orchestrator/
|   |   +-- __init__.py
|   |   +-- test_pipeline.py     # 35 tests
|   +-- test_storage/
|       +-- __init__.py
|       +-- test_database.py     # 33 tests
|
+-- .sisyphus/                # Work tracking
|   +-- plans/
|   +-- notepads/
|
+-- pyproject.toml
+-- README.md
+-- IDEA.md                   # Full specification
+-- AGENTS.md                 # This file
+-- .gitignore
```

---

## Tech Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| Language | Python 3.11+ | Strict typing required |
| TUI | Textual | Latest version |
| CLI | Typer | With Click backend |
| Async | asyncio | Built-in, no third-party |
| Config | PyYAML + Pydantic | YAML with validation |
| Database | SQLite | WAL mode, single file |
| Models | Pydantic / dataclasses | Validation and serialization |
| Templates | Jinja2 | HTML report generation |
| HTTP Client | httpx | Async HTTP requests |
| Testing | unittest | Standard library (218 tests) |
| Isolation | Docker | Preferred runner |

---

## Coding Standards

### Absolute Requirements

```yaml
constraints:
  max_nesting_levels: 3          # Use guard clauses
  max_function_loc: 70           # Split if larger
  typing: strict                 # All functions typed
  error_handling: explicit       # No silent failures
  path_handling: pathlib only    # Never os.path
  data_models: pydantic | dataclasses
  testing_framework: unittest    # Standard library
```

### Path Handling (CRITICAL)

```python
# CORRECT - Always use pathlib
from pathlib import Path

config_path = Path.home() / ".config" / "galehuntui"
data_dir = Path.home() / ".local" / "share" / "galehuntui"
tools_bin = Path(__file__).parent.parent / "tools" / "bin"

# Check existence
if not config_path.exists():
    config_path.mkdir(parents=True)

# Read/write
content = config_path.read_text()
config_path.write_text(yaml_content)

# WRONG - Never use os.path or string concatenation
import os
config_path = os.path.expanduser("~") + "/.config/galehuntui"  # FORBIDDEN
```

### Guard Clauses Pattern

```python
# CORRECT - Early returns, flat structure
def process_finding(finding: Finding | None) -> Result:
    if finding is None:
        return Result.empty()
    
    if not finding.has_evidence():
        return Result.error("No evidence")
    
    if finding.is_duplicate():
        return Result.skip("Duplicate")
    
    # Main logic at the end, not nested
    return Result.ok(normalize(finding))

# WRONG - Deep nesting
def process_finding(finding):
    if finding is not None:
        if finding.has_evidence():
            if not finding.is_duplicate():
                # Deeply nested logic
                pass
```

### Error Handling Pattern

```python
# CORRECT - Explicit, typed error handling
from galehuntui.core.exceptions import (
    ToolNotFoundError,
    ToolTimeoutError,
    ToolExecutionError,
)

async def run_tool(tool: str, inputs: list[str]) -> ToolResult:
    try:
        result = await execute(tool, inputs)
        return ToolResult.success(result)
    except ToolNotFoundError as e:
        logger.error(f"Tool not found: {tool}")
        return ToolResult.error(str(e))
    except ToolTimeoutError:
        logger.warning(f"Tool timeout: {tool}")
        return ToolResult.timeout()
    except ToolExecutionError as e:
        logger.error(f"Execution failed: {e}")
        return ToolResult.error(str(e))

# WRONG - Bare except, silent failures
async def run_tool(tool, inputs):
    try:
        return await execute(tool, inputs)
    except:  # FORBIDDEN
        pass  # FORBIDDEN - silent failure
```

### Type Hints (Required)

```python
from typing import AsyncIterator, Optional
from collections.abc import Callable, Sequence

# All functions MUST have type hints
async def classify_urls(
    urls: Sequence[str],
    rules: list[ClassificationRule],
    *,
    strict: bool = False,
    max_concurrent: int = 10,
) -> list[ClassificationResult]:
    """Classify URLs according to injection type."""
    ...

# Use Optional for nullable
def get_finding(finding_id: str) -> Optional[Finding]:
    ...

# Use | for unions (Python 3.10+)
def process(data: str | bytes) -> Result:
    ...
```

### Async Patterns

```python
# CORRECT - Proper async context management
async def scan_target(target: str) -> ScanResult:
    async with aiohttp.ClientSession() as session:
        tasks = [
            scan_subdomain(session, sub)
            for sub in subdomains
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return process_results(results)

# CORRECT - Streaming output
async def stream_tool_output(
    tool: str,
    config: ToolConfig,
) -> AsyncIterator[str]:
    process = await asyncio.create_subprocess_exec(
        tool,
        *config.args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    
    async for line in process.stdout:
        yield line.decode().strip()
```

---

## Core Data Models (Implemented)

### Finding Model

```python
# src/galehuntui/core/models.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from galehuntui.core.constants import Severity, Confidence

@dataclass
class Finding:
    id: str
    run_id: str
    type: str
    severity: Severity
    confidence: Confidence
    host: str
    url: str
    title: str
    tool: str
    timestamp: datetime
    parameter: Optional[str] = None
    description: Optional[str] = None
    evidence_paths: list[str] = field(default_factory=list)
    reproduction_steps: list[str] = field(default_factory=list)
    remediation: Optional[str] = None
    references: list[str] = field(default_factory=list)
```

### ToolResult Model

```python
@dataclass
class ToolResult:
    tool_name: str
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    output_path: Optional[Path] = None
    error_message: Optional[str] = None
    
    @classmethod
    def success_result(cls, tool_name: str, stdout: str, ...) -> "ToolResult": ...
    
    @classmethod
    def error_result(cls, tool_name: str, error: str, ...) -> "ToolResult": ...
```

### ToolConfig Model

```python
@dataclass
class ToolConfig:
    timeout: int = 300
    rate_limit: Optional[int] = None
    threads: int = 10
    output_format: str = "json"
    extra_args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
```

### RunMetadata Model

```python
@dataclass
class RunMetadata:
    id: str
    target: str
    profile: str
    mode: str
    status: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    current_stage: Optional[str] = None
    error_message: Optional[str] = None
    findings_count: int = 0
    scope_config: Optional[dict] = None
```

---

## Tool Adapter Contract (Implemented)

Every tool adapter MUST implement this interface:

```python
# src/galehuntui/tools/base.py

from abc import ABC, abstractmethod
from typing import AsyncIterator
from pathlib import Path

class ToolAdapter(ABC):
    """Base class for all tool adapters."""
    
    name: str
    required: bool = True
    docker_image: Optional[str] = None
    github_repo: Optional[str] = None
    
    def __init__(self, bin_path: Path):
        self.bin_path = bin_path
    
    @abstractmethod
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
        output_path: Path,
    ) -> list[str]:
        """Build command line arguments."""
        pass
    
    @abstractmethod
    def parse_output(self, raw: str) -> list[Finding]:
        """Parse tool output to normalized findings."""
        pass
    
    async def run(
        self,
        inputs: list[str],
        config: ToolConfig,
        output_path: Path,
    ) -> ToolResult:
        """Execute tool (base implementation provided)."""
        ...
    
    async def stream(
        self,
        inputs: list[str],
        config: ToolConfig,
        output_path: Path,
    ) -> AsyncIterator[str]:
        """Stream tool output (base implementation provided)."""
        ...
    
    async def check_available(self) -> bool:
        """Check if tool is available."""
        ...
    
    async def get_version(self) -> str:
        """Get tool version."""
        ...
```

---

## Pipeline Stages

The core pipeline processes targets through these stages:

| Stage | Tool(s) | Input | Output | Required |
|-------|---------|-------|--------|----------|
| **Subdomain Enumeration** | subfinder | domain | subdomains.json | Yes |
| **DNS Resolution** | dnsx | subdomains | resolved_hosts.json | Yes |
| **HTTP Probing** | httpx | hosts | live_hosts.json | Yes |
| **Web Crawling** | katana, gau | live hosts | urls.json | Yes |
| **URL Classification** | (internal) | urls | classified_urls.json | Yes |
| **Vulnerability Scanning** | nuclei | urls | nuclei_findings.json | Yes |
| **XSS Testing** | dalfox | xss_candidates | xss_findings.json | Profile |
| **Fuzzing** | ffuf | endpoints | fuzz_results.json | Profile |
| **SQLi Testing** | sqlmap | sqli_candidates | sqli_findings.json | Mode |

---

## URL Classification (Implemented)

URLs are classified for targeted testing:

| Group | Pattern Indicators | Injection Type |
|-------|-------------------|----------------|
| `xss_candidates` | Reflected params, query strings | XSS |
| `sqli_candidates` | ID params, numeric inputs | SQL Injection |
| `redirect_candidates` | URL params, goto/redirect | Open Redirect |
| `ssrf_candidates` | URL/host params, callbacks | SSRF |
| `generic` | Other parameterized URLs | General Testing |

### Static Extension Filter

```python
# src/galehuntui/core/constants.py

STATIC_EXTENSIONS = {
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.bmp', '.tiff',
    # Documents
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    # Assets
    '.css', '.js', '.woff', '.woff2', '.ttf', '.eot', '.otf',
    # Media
    '.mp3', '.mp4', '.avi', '.mov', '.webm', '.wav', '.flac', '.ogg',
    # Archives
    '.zip', '.tar', '.gz', '.rar', '.7z', '.bz2',
    # Other
    '.map', '.min.js', '.min.css',
}
```

---

## Engagement Modes (Implemented)

Three engagement modes control feature availability and rate limiting:

| Feature | Bug Bounty | Authorized | Aggressive |
|---------|------------|------------|------------|
| **Rate Limit (global)** | 30/s | 100/s | 500/s |
| **Rate Limit (per-host)** | 5/s | 20/s | 100/s |
| **Concurrency** | 5-10 | 20-50 | 50-100 |
| **SQLi Data Dump** | Disabled | On-demand | Enabled |
| **Brute Force** | Disabled | On-demand | Enabled |
| **Auth Testing** | Disabled | Enabled | Enabled |
| **DoS Probes** | Disabled | Disabled | On-demand |
| **Scope Enforcement** | Strict | Enforced | Optional |

```python
# src/galehuntui/core/constants.py

class EngagementMode(str, Enum):
    BUGBOUNTY = "bugbounty"
    AUTHORIZED = "authorized"
    AGGRESSIVE = "aggressive"

RATE_LIMITS = {
    EngagementMode.BUGBOUNTY: {"global": 30, "per_host": 5},
    EngagementMode.AUTHORIZED: {"global": 100, "per_host": 20},
    EngagementMode.AGGRESSIVE: {"global": 500, "per_host": 100},
}

CONCURRENCY_LIMITS = {
    EngagementMode.BUGBOUNTY: {"min": 5, "max": 10},
    EngagementMode.AUTHORIZED: {"min": 20, "max": 50},
    EngagementMode.AGGRESSIVE: {"min": 50, "max": 100},
}
```

---

## TUI Screens (Implemented)

The application has 11 main screens:

| Screen | Purpose | Key Bindings |
|--------|---------|--------------|
| **Home Dashboard** | Overview, recent runs, quick actions | N, Q, T, S, P |
| **New Run** | Configure and start new scan | Enter, Tab, Esc |
| **Run Detail** | Monitor running/completed scan | C, P, E, O |
| **Tools Manager** | Install, update, verify tools | U, R, I, A |
| **Dependencies Manager** | Manage wordlists, templates | U, E, D |
| **Settings** | Application configuration | Ctrl+S, R |
| **Profiles Editor** | Create/edit scan profiles | Ctrl+S, T |
| **Scope Editor** | Define target scope | Ctrl+S, V, P |
| **Finding Detail** | View vulnerability details | E, O, arrows |
| **Help** | Keyboard shortcuts, docs | /, arrows |
| **Setup Wizard** | First-run configuration | Enter, arrows |

### Global Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `?` | Show help |
| `Esc` | Back / Cancel |
| `Ctrl+Q` | Quit |
| `Ctrl+S` | Settings / Save |
| `Ctrl+T` | Tools Manager |
| `Ctrl+N` | New Run |
| `Tab` | Next field |
| `/` | Search |
| `j/k` or arrows | Navigate |
| `g/G` | Top/Bottom |

---

## Storage Layout

```
~/.local/share/galehuntui/
+-- galehuntui.db              # SQLite database (WAL mode)
+-- logs/
|   +-- app.log
+-- audit/                      # Audit logs (compliance)
|   +-- audit_2024-02.log
+-- runs/
    +-- <run_id>/
        +-- metadata.json       # Run configuration
        +-- config.yaml         # Scope and settings used
        +-- artifacts/          # Raw tool outputs
        |   +-- subfinder/
        |   |   +-- output.json
        |   +-- httpx/
        |   +-- nuclei/
        |   +-- ...
        +-- evidence/           # Finding evidence
        |   +-- screenshots/
        |   +-- requests/
        |   +-- responses/
        +-- reports/
            +-- report.html
            +-- findings.json
            +-- summary.json
```

---

## Configuration Files

### Scope Configuration

```yaml
# configs/scope.example.yaml
target:
  domain: example.com
  
scope:
  allowlist:
    - "*.example.com"
    - "api.example.com"
    
  denylist:
    - "admin.example.com"
    - "*.staging.example.com"
    
  exclusions:
    paths:
      - "/logout"
      - "/reset-password"
    extensions:
      - ".pdf"
      - ".doc"
```

### Scan Profiles

```yaml
# configs/profiles.yaml
profiles:
  quick:
    description: "Fast reconnaissance only"
    steps: [subfinder, dnsx, httpx]
    concurrency: 20
    rate_limit: 50
    timeout: 300
    
  standard:
    description: "Balanced recon + vuln scan"
    steps: [subfinder, dnsx, httpx, katana, gau, nuclei]
    concurrency: 10
    rate_limit: 30
    timeout: 1800
    
  deep:
    description: "Full pipeline with injection testing"
    steps: [subfinder, dnsx, httpx, katana, gau, nuclei, dalfox, ffuf, sqlmap]
    concurrency: 5
    rate_limit: 10
    timeout: 7200
```

---

## Exception Hierarchy (Implemented)

```python
# src/galehuntui/core/exceptions.py

class GaleHunTUIError(Exception):
    """Base exception for all GaleHunTUI errors."""
    pass

# Configuration errors
class ConfigError(GaleHunTUIError): pass
class InvalidScopeError(ConfigError): pass
class ProfileNotFoundError(ConfigError): pass

# Tool errors
class ToolError(GaleHunTUIError): pass
class ToolNotFoundError(ToolError): pass
class ToolInstallError(ToolError): pass
class ToolTimeoutError(ToolError): pass
class ToolExecutionError(ToolError): pass

# Pipeline errors
class PipelineError(GaleHunTUIError): pass
class ScopeViolationError(PipelineError): pass
class RateLimitExceededError(PipelineError): pass

# Storage errors
class StorageError(GaleHunTUIError): pass
class ArtifactNotFoundError(StorageError): pass
class DatabaseError(StorageError): pass

# Runner errors
class RunnerError(GaleHunTUIError): pass
class DockerNotAvailableError(RunnerError): pass
```

---

## Testing (Implemented)

### Test Structure

```
tests/
+-- test_classifier/
|   +-- __init__.py
|   +-- test_classifier.py      # 40 tests - URLClassifier
|   +-- test_normalizer.py      # 32 tests - URLNormalizer, URLDeduper
+-- test_tools/
|   +-- __init__.py
|   +-- test_adapters/
|       +-- __init__.py
|       +-- test_httpx.py       # 21 tests
|       +-- test_nuclei.py      # 31 tests
|       +-- test_subfinder.py   # 26 tests
+-- test_orchestrator/
|   +-- __init__.py
|   +-- test_pipeline.py        # 35 tests
+-- test_storage/
    +-- __init__.py
    +-- test_database.py        # 33 tests
```

### Running Tests

```bash
# Ensure virtual environment is activated
source .venv/bin/activate

# Run all tests
PYTHONPATH=src python -m unittest discover tests -v

# Run specific module
PYTHONPATH=src python -m unittest tests.test_classifier.test_classifier -v

# Run with coverage (if pytest installed)
pip install pytest pytest-cov
pytest tests/ --cov=galehuntui --cov-report=term-missing
```

> **Note**: Always run tests within a virtual environment to ensure consistent behavior.

---

## CLI Commands Reference (Implemented)

```bash
# TUI mode
galehuntui tui

# CLI scan
galehuntui run <target> \
  --profile standard \
  --scope configs/scope.example.yaml \
  --mode authorized

# Tool management
galehuntui tools init
galehuntui tools install --all
galehuntui tools install subfinder nuclei
galehuntui tools update --all
galehuntui tools list
galehuntui tools verify

# Dependency management
galehuntui deps install --all
galehuntui deps update nuclei-templates
galehuntui deps clean

# Run management
galehuntui runs list
galehuntui runs show <run_id>
galehuntui runs delete <run_id>

# Export
galehuntui export <run_id> --format html
galehuntui export <run_id> --format json
```

---

## Quick Reference Card

| What | Where | How |
|------|-------|-----|
| Add tool adapter | `src/galehuntui/tools/adapters/` | Inherit `ToolAdapter`, implement `build_command()` and `parse_output()` |
| Add TUI screen | `src/galehuntui/ui/screens/` | Extend Textual `Screen`, register in `app.py` |
| Add config option | `src/galehuntui/core/config.py` | Update Pydantic model |
| Add exception | `src/galehuntui/core/exceptions.py` | Inherit `GaleHunTUIError` |
| Add CLI command | `src/galehuntui/cli.py` | Use Typer decorator |
| Add test | `tests/test_{module}/` | unittest TestCase class |
| Style TUI | `src/galehuntui/ui/styles/main.tcss` | Textual CSS |

---

## Development Workflow

### Adding a New Tool Adapter

1. Create adapter: `src/galehuntui/tools/adapters/{toolname}.py`
2. Inherit from `ToolAdapter` class
3. Implement required methods:
   - `build_command()` - Build CLI arguments
   - `parse_output()` - Parse JSON/text output to Findings
4. Add to `__init__.py` exports
5. Add tests in `tests/test_tools/test_adapters/test_{toolname}.py`

### Adding a New TUI Screen

1. Create screen: `src/galehuntui/ui/screens/{screen_name}.py`
2. Define Textual Screen class with compose() method
3. Add keyboard bindings with `@on()` decorators
4. Register in `app.py` SCREENS dict
5. Add navigation from relevant screens
6. Style in `styles/main.tcss`

---

## Critical Rules

### Evidence Requirement

> **CRITICAL**: No finding shall be recorded without corresponding evidence files.

Every `Finding` object MUST have:
- Request/response data saved
- Screenshot (if applicable)
- Tool raw output preserved

### Scope Enforcement

All tools MUST respect scope configuration:
- Check URL against allowlist/denylist before processing
- Log out-of-scope attempts to audit log
- Block or warn based on engagement mode

### Rate Limiting

All HTTP operations MUST respect rate limits:
- Global limit applies across all tools
- Per-host limit prevents target overload
- Adaptive backoff on slow responses or 429s

### Audit Logging

Sensitive operations MUST be logged:
- Mode changes
- Aggressive feature enablement
- Data extraction attempts
- Out-of-scope access attempts

---

## Dependencies Quick Reference

### Python Packages

```toml
# pyproject.toml
[project.dependencies]
textual = ">=0.50.0"
typer = ">=0.9.0"
pyyaml = ">=6.0"
pydantic = ">=2.0"
httpx = ">=0.25.0"
jinja2 = ">=3.1.0"
rich = ">=13.0.0"

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0",
    "ruff>=0.1.0",
    "mypy>=1.0",
]
```

### External Tools (Managed)

| Tool | Source | Install Method |
|------|--------|----------------|
| subfinder | projectdiscovery/subfinder | GitHub Release |
| dnsx | projectdiscovery/dnsx | GitHub Release |
| httpx | projectdiscovery/httpx | GitHub Release |
| katana | projectdiscovery/katana | GitHub Release |
| nuclei | projectdiscovery/nuclei | GitHub Release |
| gau | lc/gau | GitHub Release |
| ffuf | ffuf/ffuf | GitHub Release |
| dalfox | hahwul/dalfox | GitHub Release |
| sqlmap | sqlmapproject/sqlmap | Git Clone |
| wfuzz | xmendez/wfuzz | Git Clone |

---

## Completed Enhancements

All major roadmap items have been implemented:

### Backend Infrastructure
- [x] `tools/registry.yaml` - Tool definitions file
- [x] `tools/deps/manager.py` - Dependency manager
- [x] `tools/deps/wordlists.py` - Wordlist manager
- [x] `tools/deps/templates.py` - Template manager  
- [x] `ui/widgets/log_view.py` - Custom log widget
- [x] `ui/widgets/progress.py` - Progress widget
- [x] `ui/widgets/findings_table.py` - Findings table widget
- [x] `storage/migrations/` - Database migrations
- [x] Resume capability for long-running scans
- [x] Webhook notifications (Slack/Discord)
- [x] Plugin system for community adapters

### TUI Screen Wiring (All screens now use real backends)
- [x] `home.py` - Real stats from Database, actual run history
- [x] `new_run.py` - Triggers PipelineOrchestrator via background worker
- [x] `run_detail.py` - Polls database for real-time progress/findings
- [x] `deps_manager.py` - Uses real DependencyManager for git operations
- [x] `settings.py` - Persists config to ~/.config/galehuntui/config.yaml
- [x] `profiles.py` - Reads/writes profiles.yaml
- [x] `scope.py` - Scans filesystem for YAML scope files
- [x] `setup.py` - Real Python/Git/Docker checks, real tool installation
- [x] `tools_manager.py` - Uses real ToolInstaller
- [x] `finding_detail.py` - Displays real Finding objects
- [x] `help.py` - Static content (no backend needed)

### Core Model Enhancements
- [x] `ScopeConfig.is_in_scope()` - Full URL/pattern validation with fnmatch
- [x] `get_data_dir()` helper in config.py

---

*Last updated: 2026-02-03*
