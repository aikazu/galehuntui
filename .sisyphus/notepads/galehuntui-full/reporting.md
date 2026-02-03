# Reporting Module Implementation

## Overview
Implemented comprehensive report generation system with HTML and JSON export capabilities.

## Files Created

### 1. `src/galehuntui/reporting/generator.py` (374 lines)
- **ReportStatistics**: Dataclass for tracking finding statistics
  - Counts by severity, confidence, type, tool
  - Unique hosts and URLs tracking
  - Severity distribution percentages
  - Properties: `high_severity_count`, `severity_distribution`

- **Report**: Complete report data structure
  - Contains: run_metadata, findings, statistics, executive_summary
  - Properties: `duration_formatted`

- **ReportGenerator**: Main report generation class
  - `__init__(db: Database)`: Initialize with database instance
  - `generate_report(run_id: str) -> Report`: Generate complete report
  - `_calculate_statistics(findings) -> ReportStatistics`: Compute metrics
  - `_generate_executive_summary(run_metadata, stats) -> str`: Create summary text
  - `export_html(report, output_path)`: Export to HTML
  - `export_json(report, output_path)`: Export to JSON
  - `generate_and_export(run_id, output_dir, formats) -> dict`: All-in-one generation

### 2. `src/galehuntui/reporting/exporters/html.py` (156 lines)
- **HTMLExporter**: HTML export using Jinja2 templates
  - Jinja2 environment with auto-escaping enabled
  - Custom filters:
    - `severity_badge_class`: CSS classes for severity badges
    - `confidence_badge_class`: CSS classes for confidence badges
    - `format_datetime`: Format datetime objects
    - `format_duration`: Format seconds to human-readable duration
  - `export(report, output_path)`: Render and save HTML report

### 3. `src/galehuntui/reporting/exporters/json.py` (134 lines)
- **ReportJSONEncoder**: Custom JSON encoder
  - Handles: datetime (isoformat), Enum (value), Path (string)
  - Overrides `default(self, o)` method

- **JSONExporter**: JSON export functionality
  - Structured JSON with metadata sections:
    - `report_metadata`: Generator info, timestamp
    - `scan_metadata`: Run information
    - `statistics`: Comprehensive metrics
    - `findings`: Array of detailed findings
  - `export(report, output_path)`: Write formatted JSON

### 4. `src/galehuntui/reporting/templates/report.html.j2` (564 lines)
Professional HTML template with:
- **Styling**: Modern CSS with gradient header, cards, badges
- **Sections**:
  - Header: Target, generation timestamp
  - Scan Information: 6-card grid with run details
  - Findings Summary: Severity statistics with color-coded cards
  - Executive Summary: Pre-formatted text block
  - Detailed Findings: 
    - Summary table with sortable columns
    - Expandable detailed view for each finding
    - Evidence files, reproduction steps, remediation
- **Responsive Design**: Grid layouts, mobile-friendly
- **Color Scheme**:
  - Critical: Red (#c53030)
  - High: Orange (#dd6b20)
  - Medium: Yellow (#d69e2e)
  - Low: Green (#38a169)
  - Info: Blue (#3182ce)

### 5. `src/galehuntui/reporting/exporters/__init__.py`
Package initialization file for exporters

## Executive Summary Format
```
Security Assessment Report: {target}
======================================================================

SCAN INFORMATION
----------------------------------------------------------------------
Target:           {target}
Profile:          {profile}
Engagement Mode:  {mode}
Scan Date:        {date}
Duration:         {duration}
Status:           {state}

FINDINGS SUMMARY
----------------------------------------------------------------------
Total Findings:   {total}
Unique Hosts:     {hosts}
Unique URLs:      {urls}

Severity Breakdown:
  Critical:       {count}
  High:           {count}
  Medium:         {count}
  Low:            {count}
  Info:           {count}

Top Vulnerability Types:
  {type}              {count}
  ...

RISK ASSESSMENT
----------------------------------------------------------------------
⚠️  CRITICAL: {count} critical severity finding(s) require immediate attention.
⚠️  HIGH: {count} high severity finding(s) should be addressed urgently.
ℹ️  MODERATE: {count} medium severity finding(s) identified.
✓  No security findings identified during this scan.
```

## JSON Output Structure
```json
{
  "report_metadata": {
    "generated_at": "ISO8601",
    "generator": "GaleHunTUI",
    "version": "1.0.0"
  },
  "scan_metadata": {
    "run_id": "uuid",
    "target": "domain",
    "profile": "name",
    "engagement_mode": "bugbounty|authorized|aggressive",
    "state": "completed|failed|...",
    "created_at": "ISO8601",
    "started_at": "ISO8601",
    "completed_at": "ISO8601",
    "duration_seconds": float,
    "total_steps": int,
    "completed_steps": int,
    "failed_steps": int
  },
  "statistics": {
    "total_findings": int,
    "unique_hosts": int,
    "unique_urls": int,
    "by_severity": {
      "critical": int,
      "high": int,
      "medium": int,
      "low": int,
      "info": int
    },
    "severity_distribution": {
      "critical": float,  // percentage
      "high": float,
      "medium": float,
      "low": float,
      "info": float
    },
    "by_confidence": { "confirmed": int, "firm": int, "tentative": int },
    "by_type": { "xss": int, "sqli": int, ... },
    "by_tool": { "nuclei": int, "dalfox": int, ... }
  },
  "findings": [
    {
      "id": "uuid",
      "type": "xss|sqli|...",
      "severity": "critical|high|medium|low|info",
      "confidence": "confirmed|firm|tentative",
      "host": "example.com",
      "url": "https://...",
      "parameter": "param_name",
      "tool": "tool_name",
      "timestamp": "ISO8601",
      "title": "Finding title",
      "description": "Details...",
      "reproduction_steps": ["Step 1", "Step 2"],
      "remediation": "Fix...",
      "references": ["https://..."],
      "evidence_paths": ["evidence/file1.png"]
    }
  ]
}
```

## Usage Examples

### Generate Report
```python
from pathlib import Path
from galehuntui.storage.database import Database
from galehuntui.reporting.generator import ReportGenerator

# Initialize
db = Database(Path.home() / ".local/share/galehuntui/galehuntui.db")
generator = ReportGenerator(db)

# Generate report for a run
report = generator.generate_report(run_id="abc-123")

# Access statistics
print(f"Total findings: {report.statistics.total_findings}")
print(f"Critical: {report.statistics.critical_count}")
print(f"High severity: {report.statistics.high_severity_count}")

# Export to HTML
output_path = Path("reports/report.html")
generator.export_html(report, output_path)

# Export to JSON
json_path = Path("reports/findings.json")
generator.export_json(report, json_path)
```

### All-in-One Generation
```python
# Generate and export in one call
output_paths = generator.generate_and_export(
    run_id="abc-123",
    output_dir=Path("reports"),
    formats=["html", "json"]
)

print(f"HTML: {output_paths['html']}")
print(f"JSON: {output_paths['json']}")
```

## Statistics Calculation
The `_calculate_statistics` method processes findings to compute:
1. Total findings count
2. Counts by severity (individual counters + dictionary)
3. Counts by confidence level
4. Counts by vulnerability type
5. Counts by source tool
6. Unique hosts (set deduplication)
7. Unique URLs (set deduplication)
8. Severity distribution percentages

## Integration Points
- **Database**: Uses `Database.get_run()` and `Database.get_findings_for_run()`
- **Models**: Relies on `RunMetadata`, `Finding`, `Severity`, `Confidence`
- **Exceptions**: Raises `StorageError` on failures
- **Path Handling**: Uses `pathlib.Path` exclusively

## Dependencies
- `jinja2`: HTML template rendering
- `json`: Standard library JSON encoding
- `datetime`: Timestamp handling
- `pathlib`: Path operations

## Design Patterns
1. **Separation of Concerns**: Generator, exporters, templates separated
2. **Template Method**: Export logic delegated to specialized exporters
3. **Custom Encoding**: JSON encoder handles special types
4. **Filter Pattern**: Jinja2 custom filters for formatting

## Validation
- ✅ LSP diagnostics clean for generator.py
- ⚠️ jinja2 import not resolved (external dependency, expected)
- ⚠️ Minor JSONEncoder.default signature warning (safe, correct override)

## Future Enhancements
- PDF export support (using weasyprint or reportlab)
- Email report delivery
- Slack/Discord webhook integration
- Custom template support
- Report scheduling
- Trend analysis across multiple runs
