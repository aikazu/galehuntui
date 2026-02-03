"""Constants used throughout GaleHunTUI.

This module contains enums, default values, and static configurations
to ensure consistency across the application.
"""

from enum import Enum


class EngagementMode(Enum):
    """Engagement mode for testing."""
    BUG_BOUNTY = "bugbounty"
    AUTHORIZED = "authorized"
    AGGRESSIVE = "aggressive"


class StepStatus(Enum):
    """Pipeline step execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineStage(Enum):
    """Stages in the execution pipeline."""
    SUBDOMAIN_ENUM = "subdomain_enumeration"
    DNS_RESOLUTION = "dns_resolution"
    HTTP_PROBING = "http_probing"
    WEB_CRAWLING = "web_crawling"
    URL_CLASSIFICATION = "url_classification"
    VULN_SCANNING = "vulnerability_scanning"
    XSS_TESTING = "xss_testing"
    FUZZING = "fuzzing"
    SQLI_TESTING = "sqli_testing"


class ClassificationGroup(Enum):
    """URL classification groups."""
    XSS = "xss_candidates"
    SQLI = "sqli_candidates"
    REDIRECT = "redirect_candidates"
    SSRF = "ssrf_candidates"
    GENERIC = "generic"


class AuditEventType(str, Enum):
    """Types of events recorded in the audit log."""
    RUN_START = "run_start"
    RUN_FINISH = "run_finish"
    TOOL_START = "tool_start"
    TOOL_FINISH = "tool_finish"
    SCOPE_VIOLATION = "scope_violation"
    MODE_CHANGE = "mode_change"
    FEATURE_TOGGLE = "feature_toggle"


# Static extensions to filter out during crawling/classification
STATIC_EXTENSIONS = {
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
    # Documents
    '.pdf', '.doc', '.docx', '.xls', '.xlsx',
    # Assets
    '.css', '.js', '.woff', '.woff2', '.ttf', '.eot',
    # Media
    '.mp3', '.mp4', '.avi', '.mov', '.webm',
    # Archives
    '.zip', '.tar', '.gz', '.rar',
}


# Mode-specific rate limits and concurrency
RATE_LIMITS = {
    EngagementMode.BUG_BOUNTY: {
        "global": 30,
        "per_host": 5,
        "concurrency": 10,
    },
    EngagementMode.AUTHORIZED: {
        "global": 100,
        "per_host": 20,
        "concurrency": 50,
    },
    EngagementMode.AGGRESSIVE: {
        "global": 500,
        "per_host": 100,
        "concurrency": 100,
    }
}

CONCURRENCY_LIMITS = {
    EngagementMode.BUG_BOUNTY: {"min": 5, "max": 10},
    EngagementMode.AUTHORIZED: {"min": 20, "max": 50},
    EngagementMode.AGGRESSIVE: {"min": 50, "max": 100},
}


# Application-wide defaults
DEFAULTS = {
    "timeout": 1800,
    "concurrency": 10,
    "rate_limit": "30/s",
    "global_rate_limit": 30,
    "per_host_rate_limit": 5,
}
