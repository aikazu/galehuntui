"""Core data models for GaleHunTUI.

This module defines all core data structures used throughout the application,
including findings, tool configurations, run states, and scan profiles.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import fnmatch

from galehuntui.core.constants import EngagementMode, StepStatus, DEFAULTS


# ============================================================================
# Enums
# ============================================================================

class Severity(Enum):
    """Finding severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Confidence(Enum):
    """Finding confidence levels."""
    CONFIRMED = "confirmed"
    FIRM = "firm"
    TENTATIVE = "tentative"


class RunState(Enum):
    """Run execution states."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ============================================================================
# Finding Model
# ============================================================================

@dataclass
class Finding:
    """Normalized security finding from tool output.
    
    All findings MUST include evidence files (screenshots, request/response data).
    Evidence paths are relative to the run's evidence directory.
    """
    id: str                                 # UUID
    run_id: str                             # Parent run reference
    type: str                               # Vulnerability type (xss, sqli, etc.)
    severity: Severity
    confidence: Confidence
    host: str
    url: str
    parameter: Optional[str]
    evidence_paths: list[str]               # Paths to evidence files
    tool: str                               # Source tool name
    timestamp: datetime
    
    # Extended fields
    title: str
    description: Optional[str] = None
    reproduction_steps: list[str] = field(default_factory=list)
    remediation: Optional[str] = None
    references: list[str] = field(default_factory=list)
    
    def has_evidence(self) -> bool:
        """Check if finding has evidence files."""
        return len(self.evidence_paths) > 0


# ============================================================================
# Tool Models
# ============================================================================

@dataclass
class ToolResult:
    """Result from tool execution."""
    stdout: str
    stderr: str
    exit_code: int
    duration: float                         # Execution time in seconds
    output_path: Path                       # Path to raw output file
    
    @property
    def success(self) -> bool:
        """Check if tool execution was successful."""
        return self.exit_code == 0


@dataclass
class ToolConfig:
    """Configuration for tool execution."""
    name: str
    args: list[str] = field(default_factory=list)
    timeout: int = 300                      # Timeout in seconds
    rate_limit: Optional[int] = None        # Requests per second
    output_format: str = "json"             # json, text
    env: dict[str, str] = field(default_factory=dict)


# ============================================================================
# Scan Profile Model
# ============================================================================

@dataclass
class ScanProfile:
    """Scan profile defining pipeline steps and execution parameters."""
    name: str
    description: str
    steps: list[str]                        # Tool names in execution order
    concurrency: int = DEFAULTS["concurrency"]
    rate_limit: str = DEFAULTS["rate_limit"]
    timeout: int = DEFAULTS["timeout"]
    use_cases: list[str] = field(default_factory=list)
    
    def get_rate_limit_value(self) -> int:
        """Parse rate limit string to integer value.
        
        Returns:
            Requests per second as integer.
        """
        # Parse format like "30/s" or "100/s"
        if "/" in self.rate_limit:
            return int(self.rate_limit.split("/")[0])
        return int(self.rate_limit)


# ============================================================================
# Run Configuration Model
# ============================================================================

@dataclass
class RunConfig:
    """Configuration for a scan run."""
    target: str                             # Target domain
    profile: str                            # Profile name
    scope_file: Path                        # Path to scope configuration
    engagement_mode: EngagementMode
    
    # Rate limiting
    rate_limit_global: int = DEFAULTS["global_rate_limit"]
    rate_limit_per_host: int = DEFAULTS["per_host_rate_limit"]
    
    # Execution parameters
    concurrency: int = DEFAULTS["concurrency"]
    timeout: int = DEFAULTS["timeout"]
    
    # Pipeline configuration
    enabled_steps: list[str] = field(default_factory=list)
    
    # Output options
    generate_html_report: bool = True
    export_json: bool = True
    save_artifacts: bool = True
    notify_on_completion: bool = False
    
    # Advanced options
    validate_scope: bool = True
    custom_args: dict[str, list[str]] = field(default_factory=dict)


# ============================================================================
# Run State Model
# ============================================================================

@dataclass
class RunMetadata:
    """Metadata for a scan run."""
    id: str                                 # UUID
    target: str
    profile: str
    engagement_mode: EngagementMode
    state: RunState
    
    # Timestamps
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Progress tracking
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    
    # Results summary
    total_findings: int = 0
    findings_by_severity: dict[str, int] = field(default_factory=dict)
    
    # Paths
    run_dir: Path = field(default=Path())
    artifacts_dir: Path = field(default=Path())
    evidence_dir: Path = field(default=Path())
    reports_dir: Path = field(default=Path())
    
    @property
    def progress_percentage(self) -> float:
        """Calculate run progress as percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100
    
    @property
    def duration(self) -> Optional[float]:
        """Calculate run duration in seconds."""
        if self.started_at is None:
            return None
        end_time = self.completed_at or datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    @property
    def is_active(self) -> bool:
        """Check if run is currently active."""
        return self.state in (RunState.RUNNING, RunState.PAUSED)
    
    @property
    def is_finished(self) -> bool:
        """Check if run has finished (successfully or not)."""
        return self.state in (RunState.COMPLETED, RunState.FAILED, RunState.CANCELLED)


# ============================================================================
# Pipeline Step Model
# ============================================================================

@dataclass
class PipelineStep:
    """Individual step in the execution pipeline."""
    name: str                               # Tool name
    status: StepStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None        # Duration in seconds
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    output_path: Optional[Path] = None
    findings_count: int = 0
    
    @property
    def is_running(self) -> bool:
        """Check if step is currently running."""
        return self.status == StepStatus.RUNNING
    
    @property
    def is_finished(self) -> bool:
        """Check if step has finished."""
        return self.status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED)


# ============================================================================
# Scope Configuration Model
# ============================================================================

@dataclass
class ScopeConfig:
    """Target scope configuration."""
    target_domain: str
    allowlist: list[str] = field(default_factory=list)
    denylist: list[str] = field(default_factory=list)
    excluded_paths: list[str] = field(default_factory=list)
    excluded_extensions: list[str] = field(default_factory=list)
    
    def is_in_scope(self, url: str) -> bool:
        """Check if URL is within scope.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL is in scope, False otherwise
        """
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower()
            path = parsed.path.lower()
            
            if not host and not parsed.scheme:
                if "/" in url:
                    host = url.split("/")[0].lower()
                    path = "/" + "/".join(url.split("/")[1:])
                else:
                    host = url.lower()
                    path = ""
            
            for pattern in self.denylist:
                if fnmatch.fnmatch(host, pattern.lower()):
                    return False
            
            if self.allowlist:
                allowed = False
                for pattern in self.allowlist:
                    if fnmatch.fnmatch(host, pattern.lower()):
                        allowed = True
                        break
                if not allowed:
                    return False
            
            for excluded_path in self.excluded_paths:
                if path.startswith(excluded_path.lower()):
                    return False
            
            for excluded_ext in self.excluded_extensions:
                if path.endswith(excluded_ext.lower()):
                    return False
            
            return True
            
        except Exception:
            return False


# ============================================================================
# Classification Models
# ============================================================================

@dataclass
class ClassificationResult:
    """Result of URL classification."""
    url: str
    groups: list[str]                       # Classification groups (xss_candidates, sqli_candidates, etc.)
    confidence: float = 1.0                 # Classification confidence (0.0-1.0)
    
    @property
    def is_xss_candidate(self) -> bool:
        """Check if URL is classified as XSS candidate."""
        return "xss_candidates" in self.groups
    
    @property
    def is_sqli_candidate(self) -> bool:
        """Check if URL is classified as SQLi candidate."""
        return "sqli_candidates" in self.groups
    
    @property
    def is_redirect_candidate(self) -> bool:
        """Check if URL is classified as redirect candidate."""
        return "redirect_candidates" in self.groups
    
    @property
    def is_ssrf_candidate(self) -> bool:
        """Check if URL is classified as SSRF candidate."""
        return "ssrf_candidates" in self.groups
    
    @property
    def is_generic(self) -> bool:
        """Check if URL is classified as generic."""
        return "generic" in self.groups
