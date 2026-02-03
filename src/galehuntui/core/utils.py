"""Core utility functions for GaleHunTUI."""

from dataclasses import dataclass
from typing import Sequence

from galehuntui.core.models import Finding, Severity


@dataclass
class FindingCounts:
    """Categorized finding counts."""
    subdomain: int = 0
    live_domain: int = 0
    findings: int = 0
    info: int = 0

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "subdomain": self.subdomain,
            "live_domain": self.live_domain,
            "findings": self.findings,
            "info": self.info,
        }


def classify_finding(finding: Finding) -> str:
    """
    Classify a single finding into a category.
    
    Returns one of: 'subdomain', 'live_domain', 'info', 'findings'
    """
    ftype = finding.type.lower() if finding.type else ""
    tool = finding.tool.lower() if finding.tool else ""
    
    # Subdomain/DNS results from subfinder or dnsx
    if ftype in ("subdomain", "dns_record") or tool in ("subfinder", "dnsx"):
        return "subdomain"
    
    # Live host probing results from httpx
    if ftype == "http_probe" or tool == "httpx":
        return "live_domain"
    
    # INFO severity findings (non-vulnerability informational items)
    if finding.severity == Severity.INFO:
        return "info"
    
    # Actual vulnerability findings
    return "findings"


def categorize_findings(findings: Sequence[Finding]) -> FindingCounts:
    """
    Categorize a collection of findings into counts by type.
    
    Categories:
    - subdomain: Subdomain enumeration results (subfinder, dnsx)
    - live_domain: HTTP probe results (httpx)
    - info: INFO severity items
    - findings: Actual vulnerability findings (non-INFO severity)
    
    Args:
        findings: Sequence of Finding objects to categorize
        
    Returns:
        FindingCounts dataclass with counts for each category
    """
    counts = FindingCounts()
    
    for finding in findings:
        category = classify_finding(finding)
        if category == "subdomain":
            counts.subdomain += 1
        elif category == "live_domain":
            counts.live_domain += 1
        elif category == "info":
            counts.info += 1
        else:
            counts.findings += 1
    
    return counts
