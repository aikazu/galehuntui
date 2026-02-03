# GaleHunTUI

> **Orchestrated Web Pentest TUI** — A Terminal-based Automated Web Pentesting Application for Security Professionals on Linux.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

---

## Overview

**GaleHunTUI** is a powerful terminal-based application that orchestrates automated web penetration testing workflows. It provides both a rich TUI (Terminal User Interface) built with [Textual](https://textual.textualize.io/) and a comprehensive CLI built with [Typer](https://typer.tiangolo.com/).

The application supports various security testing scenarios — from **bug bounty hunting** to **full blackbox penetration testing** — with a structured, reproducible, and customizable pipeline.

### Vision

```
Reconnaissance → Vulnerability Scanning → Targeted Injection → Comprehensive Reporting
```

### Key Features

| Feature | Description |
|---------|-------------|
| **Dual Interface** | Full-featured TUI for interactive use, CLI for automation |
| **11 Integrated Tools** | subfinder, dnsx, httpx, katana, gau, nuclei, dalfox, ffuf, sqlmap, hydra, wfuzz |
| **Smart Classification** | Automatic URL classification for targeted testing (XSS, SQLi, SSRF, etc.) |
| **Flexible Runners** | Docker-first approach with transparent local fallback |
| **3 Engagement Modes** | Bug Bounty, Authorized, and Aggressive modes with appropriate safeguards |
| **Evidence Storage** | Every finding includes reproducible evidence |
| **Professional Reports** | HTML and JSON export with executive summaries |

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage](#usage)
  - [TUI Mode](#tui-mode)
  - [CLI Mode](#cli-mode)
- [Configuration](#configuration)
  - [Scope Configuration](#scope-configuration)
  - [Scan Profiles](#scan-profiles)
  - [Engagement Modes](#engagement-modes)
- [Pipeline Stages](#pipeline-stages)
- [Tool Management](#tool-management)
- [Architecture](#architecture)
- [Development](#development)
- [Testing](#testing)
- [License](#license)

---

## Installation

### Prerequisites

- Python 3.11 or higher
- Linux (Debian/Arch-based distributions)
- Docker (recommended) or local tool installations

### Install from Source

```bash
# Clone the repository
git clone https://github.com/yourusername/galehuntui.git
cd galehuntui

# Install in development mode
pip install -e .

# Verify installation
galehuntui --version
```

### Install Dependencies

```bash
# Install development dependencies
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Initialize Tools

```bash
# Initialize tool directory structure
galehuntui tools init

# Install all required tools
galehuntui tools install --all

# Verify installations
galehuntui tools verify
```

### 2. Launch TUI

```bash
galehuntui tui
```

### 3. Or Run a Quick Scan via CLI

```bash
galehuntui run example.com --profile quick --mode bugbounty
```

---

## Usage

### TUI Mode

Launch the interactive terminal interface:

```bash
galehuntui tui
```

#### TUI Screens

| Screen | Purpose | Key Bindings |
|--------|---------|--------------|
| **Home Dashboard** | Overview, recent runs, quick actions | `N`, `Q`, `T`, `S`, `P` |
| **New Run** | Configure and start new scan | `Enter`, `Tab`, `Esc` |
| **Run Detail** | Monitor running/completed scan | `C`, `P`, `E`, `O` |
| **Tools Manager** | Install, update, verify tools | `U`, `R`, `I`, `A` |
| **Dependencies Manager** | Manage wordlists, templates | `U`, `E`, `D` |
| **Settings** | Application configuration | `Ctrl+S`, `R` |
| **Profiles Editor** | Create/edit scan profiles | `Ctrl+S`, `T` |
| **Scope Editor** | Define target scope | `Ctrl+S`, `V`, `P` |
| **Finding Detail** | View vulnerability details | `E`, `O`, arrows |
| **Help** | Keyboard shortcuts, docs | `/`, arrows |
| **Setup Wizard** | First-run configuration | `Enter`, arrows |

#### Global Keyboard Shortcuts

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

### CLI Mode

Run scans and manage the application from the command line:

```bash
# Execute a scan
galehuntui run <target> [OPTIONS]

# Options:
#   -p, --profile   Scan profile (quick, standard, deep)
#   -m, --mode      Engagement mode (bugbounty, authorized, aggressive)
#   -s, --scope     Scope configuration file
#   -o, --output    Output directory
#   -v, --verbose   Verbose output

# Examples:
galehuntui run example.com --profile standard --mode authorized
galehuntui run example.com -p deep -m aggressive -s scope.yaml
```

#### Tool Management

```bash
# Initialize tools directory
galehuntui tools init

# Install specific tools
galehuntui tools install subfinder httpx nuclei

# Install all tools
galehuntui tools install --all

# Update tools
galehuntui tools update --all

# List installed tools
galehuntui tools list

# Verify installations
galehuntui tools verify
```

#### Dependency Management

```bash
# Install all dependencies (templates, wordlists)
galehuntui deps install --all

# Update nuclei templates
galehuntui deps update nuclei-templates

# Clean old dependencies
galehuntui deps clean
```

#### Run Management

```bash
# List recent runs
galehuntui runs list --limit 10

# Show run details
galehuntui runs show <run_id>

# Delete a run
galehuntui runs delete <run_id> --force
```

#### Export Reports

```bash
# Export as HTML
galehuntui export <run_id> --format html --output report.html

# Export as JSON
galehuntui export <run_id> --format json --output findings.json
```

---

## Configuration

### Scope Configuration

Define target scope in YAML format:

```yaml
# configs/scope.yaml
target:
  domain: example.com

scope:
  allowlist:
    - "*.example.com"
    - "api.example.com"
    - "app.example.com"

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

Three built-in profiles with customizable settings:

| Profile | Description | Tools | Rate Limit |
|---------|-------------|-------|------------|
| **quick** | Fast reconnaissance only | subfinder, dnsx, httpx | 50/s |
| **standard** | Balanced recon + vuln scan | + katana, gau, nuclei | 30/s |
| **deep** | Full pipeline with injection testing | + dalfox, ffuf, sqlmap | 10/s |

Custom profiles can be defined in `configs/profiles.yaml`:

```yaml
profiles:
  custom:
    description: "My custom profile"
    steps: [subfinder, httpx, nuclei, dalfox]
    concurrency: 15
    rate_limit: 25/s
    timeout: 3600
```

### Engagement Modes

| Mode | Use Case | Rate Limits | Features |
|------|----------|-------------|----------|
| **bugbounty** | Bug bounty programs | Conservative (30/s global, 5/s per-host) | SQLi dump disabled, brute force disabled |
| **authorized** | Authorized pentests | Moderate (100/s global, 20/s per-host) | Full features on-demand |
| **aggressive** | Full assessments | High (500/s global, 100/s per-host) | All features enabled |

---

## Pipeline Stages

The scanning pipeline processes targets through these stages:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           PIPELINE FLOW                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  [Target Input]                                                          │
│       │                                                                  │
│       ▼                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │
│  │  Subfinder  │───▶│    DNSX     │───▶│    HTTPX    │                  │
│  │ (Subdomains)│    │ (DNS Resolve)│   │ (HTTP Probe)│                  │
│  └─────────────┘    └─────────────┘    └─────────────┘                  │
│                                              │                           │
│                                              ▼                           │
│                          ┌─────────────┬─────────────┐                  │
│                          │   Katana    │     GAU     │                  │
│                          │  (Crawling) │ (URL Archive)│                 │
│                          └─────────────┴─────────────┘                  │
│                                              │                           │
│                                              ▼                           │
│                                    ┌─────────────────┐                  │
│                                    │ URL Classifier  │                  │
│                                    │ (XSS/SQLi/SSRF) │                  │
│                                    └─────────────────┘                  │
│                                              │                           │
│                     ┌────────────────────────┼────────────────────────┐ │
│                     ▼                        ▼                        ▼ │
│              ┌───────────┐           ┌───────────┐           ┌─────────┐│
│              │  Nuclei   │           │  Dalfox   │           │  FFUF   ││
│              │(Vuln Scan)│           │(XSS Test) │           │(Fuzzing)││
│              └───────────┘           └───────────┘           └─────────┘│
│                     │                        │                        │ │
│                     └────────────────────────┼────────────────────────┘ │
│                                              ▼                           │
│                                    ┌─────────────────┐                  │
│                                    │ Report Generator│                  │
│                                    │  (HTML / JSON)  │                  │
│                                    └─────────────────┘                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Stage Details

| Stage | Tool | Input | Output |
|-------|------|-------|--------|
| Subdomain Enumeration | subfinder | domain | subdomains.json |
| DNS Resolution | dnsx | subdomains | resolved_hosts.json |
| HTTP Probing | httpx | hosts | live_hosts.json |
| Web Crawling | katana, gau | live hosts | urls.json |
| URL Classification | internal | urls | classified_urls.json |
| Vulnerability Scanning | nuclei | urls | nuclei_findings.json |
| XSS Testing | dalfox | xss_candidates | xss_findings.json |
| Fuzzing | ffuf | endpoints | fuzz_results.json |
| SQLi Testing | sqlmap | sqli_candidates | sqli_findings.json |

---

## Tool Management

### Integrated Tools

| Tool | Category | Source | Required |
|------|----------|--------|----------|
| **subfinder** | Reconnaissance | projectdiscovery/subfinder | Yes |
| **dnsx** | DNS | projectdiscovery/dnsx | Yes |
| **httpx** | HTTP Probing | projectdiscovery/httpx | Yes |
| **katana** | Crawling | projectdiscovery/katana | Yes |
| **gau** | URL Archive | lc/gau | Yes |
| **nuclei** | Vuln Scanning | projectdiscovery/nuclei | Yes |
| **dalfox** | XSS Testing | hahwul/dalfox | Profile |
| **ffuf** | Fuzzing | ffuf/ffuf | Profile |
| **sqlmap** | SQLi Testing | sqlmapproject/sqlmap | Mode |
| **hydra** | Auth Testing | vanhauser-thc/thc-hydra | Mode |
| **wfuzz** | Fuzzing | xmendez/wfuzz | Mode |

### Tool Installation

Tools are installed to `./tools/bin/` (project-local):

```bash
# Automatic installation from GitHub Releases
galehuntui tools install subfinder httpx nuclei

# All tools
galehuntui tools install --all
```

---

## Architecture

### Project Structure

```
galehuntui/
├── src/galehuntui/           # Main source code
│   ├── cli.py                # Typer CLI entry point
│   ├── core/                 # Core infrastructure
│   │   ├── config.py         # Configuration loader
│   │   ├── models.py         # Pydantic/dataclass models
│   │   ├── exceptions.py     # Exception hierarchy
│   │   └── constants.py      # Enums and constants
│   ├── orchestrator/         # Pipeline coordination
│   │   ├── pipeline.py       # Pipeline execution
│   │   ├── scheduler.py      # Async task scheduling
│   │   └── state.py          # Run state management
│   ├── runner/               # Tool execution
│   │   ├── docker.py         # Docker-based execution
│   │   └── local.py          # Local execution
│   ├── tools/                # Tool management
│   │   ├── base.py           # ToolAdapter ABC
│   │   ├── installer.py      # Tool installation
│   │   └── adapters/         # Individual tool adapters
│   ├── classifier/           # URL processing
│   ├── reporting/            # Report generation
│   ├── storage/              # Data persistence
│   └── ui/                   # Textual TUI
│       ├── app.py            # Main application
│       ├── screens/          # TUI screens
│       └── styles/           # Textual CSS
├── tools/                    # External tools (gitignored)
├── configs/                  # Configuration files
├── tests/                    # Test suite
└── pyproject.toml
```

### Data Storage

```
~/.local/share/galehuntui/
├── galehuntui.db              # SQLite database (WAL mode)
├── logs/                      # Application logs
├── audit/                     # Audit logs
└── runs/
    └── <run_id>/
        ├── metadata.json      # Run configuration
        ├── artifacts/         # Raw tool outputs
        ├── evidence/          # Finding evidence
        └── reports/           # Generated reports
```

---

## Development

### Setup Development Environment

```bash
# Clone and install
git clone https://github.com/yourusername/galehuntui.git
cd galehuntui
pip install -e ".[dev]"

# Run linting
ruff check src/

# Run type checking
mypy src/galehuntui/
```

### Code Style

- **Python 3.11+** with strict typing
- **Pathlib** for all path operations (never `os.path`)
- **Guard clauses** pattern (max 3 nesting levels)
- **Explicit error handling** (no silent failures)
- **Max 70 LOC** per function

---

## Testing

### Run Tests

```bash
# Run all tests
PYTHONPATH=src python -m unittest discover tests -v

# Run specific test module
PYTHONPATH=src python -m unittest tests.test_classifier.test_classifier -v

# Run with coverage (requires pytest)
pytest tests/ --cov=galehuntui --cov-report=term-missing
```

### Test Coverage

| Module | Tests | Coverage |
|--------|-------|----------|
| Classifier | 72 | Core classification logic |
| Tool Adapters | 78 | Command building, output parsing |
| Orchestrator | 35 | Pipeline execution, rate limiting |
| Storage | 33 | Database operations, CRUD |
| **Total** | **218** | Critical paths covered |

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Disclaimer

**GaleHunTUI** is intended for authorized security testing only. Users are responsible for ensuring they have proper authorization before testing any systems. The developers assume no liability for misuse of this tool.

---

## Acknowledgments

- [ProjectDiscovery](https://projectdiscovery.io/) for their excellent security tools
- [Textual](https://textual.textualize.io/) for the amazing TUI framework
- [Typer](https://typer.tiangolo.com/) for the intuitive CLI framework
- The security research community for continuous inspiration

---

**Made with security in mind.**
