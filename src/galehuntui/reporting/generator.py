"""Report generation for GaleHunTUI.

This module provides report generation functionality with support for
HTML and JSON export formats. Reports include executive summaries,
statistics, and detailed findings.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from galehuntui.core.exceptions import StorageError
from galehuntui.core.models import Finding, RunMetadata, Severity, Confidence
from galehuntui.storage.database import Database


# ============================================================================
# Report Statistics Model
# ============================================================================

@dataclass
class ReportStatistics:
    """Statistics for report generation."""
    total_findings: int = 0
    by_severity: dict[str, int] = field(default_factory=dict)
    by_confidence: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    by_tool: dict[str, int] = field(default_factory=dict)
    unique_hosts: int = 0
    unique_urls: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    
    @property
    def high_severity_count(self) -> int:
        """Get count of critical + high severity findings."""
        return self.critical_count + self.high_count
    
    @property
    def severity_distribution(self) -> dict[str, float]:
        """Get percentage distribution of findings by severity."""
        if self.total_findings == 0:
            return {
                "critical": 0.0,
                "high": 0.0,
                "medium": 0.0,
                "low": 0.0,
                "info": 0.0,
            }
        
        return {
            "critical": (self.critical_count / self.total_findings) * 100,
            "high": (self.high_count / self.total_findings) * 100,
            "medium": (self.medium_count / self.total_findings) * 100,
            "low": (self.low_count / self.total_findings) * 100,
            "info": (self.info_count / self.total_findings) * 100,
        }


@dataclass
class Report:
    """Complete report data structure."""
    run_metadata: RunMetadata
    findings: list[Finding]
    statistics: ReportStatistics
    executive_summary: str
    generated_at: datetime = field(default_factory=datetime.now)
    
    @property
    def duration_formatted(self) -> str:
        """Get formatted run duration."""
        if self.run_metadata.duration is None:
            return "N/A"
        
        duration = self.run_metadata.duration
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"


# ============================================================================
# Report Generator
# ============================================================================

class ReportGenerator:
    """Generate comprehensive security reports from scan results.
    
    Supports HTML and JSON export formats with executive summaries,
    statistics, and detailed findings.
    """
    
    def __init__(self, db: Database):
        """Initialize report generator.
        
        Args:
            db: Database instance for retrieving run data
        """
        self.db = db
    
    def generate_report(self, run_id: str) -> Report:
        """Generate complete report for a run.
        
        Args:
            run_id: Run identifier
            
        Returns:
            Report object with metadata, findings, and statistics
            
        Raises:
            StorageError: If run not found or data retrieval fails
        """
        # Retrieve run metadata
        run_metadata = self.db.get_run(run_id)
        if run_metadata is None:
            raise StorageError(f"Run not found: {run_id}")
        
        # Retrieve findings
        findings = self.db.get_findings_for_run(run_id)
        
        # Generate statistics
        statistics = self._calculate_statistics(findings)
        
        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            run_metadata,
            statistics
        )
        
        return Report(
            run_metadata=run_metadata,
            findings=findings,
            statistics=statistics,
            executive_summary=executive_summary,
        )
    
    def _calculate_statistics(self, findings: list[Finding]) -> ReportStatistics:
        """Calculate report statistics from findings.
        
        Args:
            findings: List of findings to analyze
            
        Returns:
            ReportStatistics object with computed metrics
        """
        stats = ReportStatistics()
        stats.total_findings = len(findings)
        
        # Track unique hosts and URLs
        unique_hosts = set()
        unique_urls = set()
        
        # Count by various dimensions
        for finding in findings:
            # By severity
            severity_key = finding.severity.value
            stats.by_severity[severity_key] = stats.by_severity.get(severity_key, 0) + 1
            
            # Update individual severity counters
            if finding.severity == Severity.CRITICAL:
                stats.critical_count += 1
            elif finding.severity == Severity.HIGH:
                stats.high_count += 1
            elif finding.severity == Severity.MEDIUM:
                stats.medium_count += 1
            elif finding.severity == Severity.LOW:
                stats.low_count += 1
            elif finding.severity == Severity.INFO:
                stats.info_count += 1
            
            # By confidence
            confidence_key = finding.confidence.value
            stats.by_confidence[confidence_key] = stats.by_confidence.get(confidence_key, 0) + 1
            
            # By type
            stats.by_type[finding.type] = stats.by_type.get(finding.type, 0) + 1
            
            # By tool
            stats.by_tool[finding.tool] = stats.by_tool.get(finding.tool, 0) + 1
            
            # Track unique hosts and URLs
            unique_hosts.add(finding.host)
            unique_urls.add(finding.url)
        
        stats.unique_hosts = len(unique_hosts)
        stats.unique_urls = len(unique_urls)
        
        return stats
    
    def _generate_executive_summary(
        self,
        run_metadata: RunMetadata,
        statistics: ReportStatistics
    ) -> str:
        """Generate executive summary text.
        
        Args:
            run_metadata: Run metadata
            statistics: Report statistics
            
        Returns:
            Executive summary as formatted text
        """
        lines = []
        
        # Header
        lines.append(f"Security Assessment Report: {run_metadata.target}")
        lines.append("=" * 70)
        lines.append("")
        
        # Scan information
        lines.append("SCAN INFORMATION")
        lines.append("-" * 70)
        lines.append(f"Target:           {run_metadata.target}")
        lines.append(f"Profile:          {run_metadata.profile}")
        lines.append(f"Engagement Mode:  {run_metadata.engagement_mode.value}")
        lines.append(f"Scan Date:        {run_metadata.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if run_metadata.duration:
            duration = run_metadata.duration
            hours = int(duration // 3600)
            minutes = int((duration % 3600) // 60)
            seconds = int(duration % 60)
            
            if hours > 0:
                duration_str = f"{hours}h {minutes}m {seconds}s"
            elif minutes > 0:
                duration_str = f"{minutes}m {seconds}s"
            else:
                duration_str = f"{seconds}s"
            
            lines.append(f"Duration:         {duration_str}")
        
        lines.append(f"Status:           {run_metadata.state.value}")
        lines.append("")
        
        # Findings summary
        lines.append("FINDINGS SUMMARY")
        lines.append("-" * 70)
        lines.append(f"Total Findings:   {statistics.total_findings}")
        lines.append(f"Unique Hosts:     {statistics.unique_hosts}")
        lines.append(f"Unique URLs:      {statistics.unique_urls}")
        lines.append("")
        
        # Severity breakdown
        lines.append("Severity Breakdown:")
        lines.append(f"  Critical:       {statistics.critical_count}")
        lines.append(f"  High:           {statistics.high_count}")
        lines.append(f"  Medium:         {statistics.medium_count}")
        lines.append(f"  Low:            {statistics.low_count}")
        lines.append(f"  Info:           {statistics.info_count}")
        lines.append("")
        
        # Top vulnerability types
        if statistics.by_type:
            lines.append("Top Vulnerability Types:")
            sorted_types = sorted(
                statistics.by_type.items(),
                key=lambda x: x[1],
                reverse=True
            )
            for vuln_type, count in sorted_types[:5]:
                lines.append(f"  {vuln_type:20} {count}")
            lines.append("")
        
        # Risk assessment
        lines.append("RISK ASSESSMENT")
        lines.append("-" * 70)
        
        if statistics.critical_count > 0:
            lines.append(f"⚠️  CRITICAL: {statistics.critical_count} critical severity "
                        f"finding(s) require immediate attention.")
        
        if statistics.high_count > 0:
            lines.append(f"⚠️  HIGH: {statistics.high_count} high severity finding(s) "
                        f"should be addressed urgently.")
        
        if statistics.high_severity_count == 0 and statistics.medium_count > 0:
            lines.append(f"ℹ️  MODERATE: {statistics.medium_count} medium severity finding(s) "
                        f"identified.")
        
        if statistics.total_findings == 0:
            lines.append("✓  No security findings identified during this scan.")
        
        lines.append("")
        
        return "\n".join(lines)
    
    def export_html(self, report: Report, output_path: Path) -> None:
        """Export report to HTML format.
        
        Args:
            report: Report object to export
            output_path: Path where HTML report will be written
            
        Raises:
            StorageError: If export fails
        """
        from galehuntui.reporting.exporters.html import HTMLExporter
        
        exporter = HTMLExporter()
        exporter.export(report, output_path)
    
    def export_json(self, report: Report, output_path: Path) -> None:
        """Export report to JSON format.
        
        Args:
            report: Report object to export
            output_path: Path where JSON report will be written
            
        Raises:
            StorageError: If export fails
        """
        from galehuntui.reporting.exporters.json import JSONExporter
        
        exporter = JSONExporter()
        exporter.export(report, output_path)
    
    def generate_and_export(
        self,
        run_id: str,
        output_dir: Path,
        formats: Optional[list[str]] = None
    ) -> dict[str, Path]:
        """Generate report and export to multiple formats.
        
        Args:
            run_id: Run identifier
            output_dir: Directory for output files
            formats: List of formats to export (default: ["html", "json"])
            
        Returns:
            Dictionary mapping format names to output file paths
            
        Raises:
            StorageError: If generation or export fails
        """
        if formats is None:
            formats = ["html", "json"]
        
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate report
        report = self.generate_report(run_id)
        
        # Export to requested formats
        output_paths = {}
        
        for fmt in formats:
            if fmt == "html":
                output_path = output_dir / "report.html"
                self.export_html(report, output_path)
                output_paths["html"] = output_path
            
            elif fmt == "json":
                output_path = output_dir / "findings.json"
                self.export_json(report, output_path)
                output_paths["json"] = output_path
            
            else:
                raise ValueError(f"Unsupported export format: {fmt}")
        
        return output_paths
