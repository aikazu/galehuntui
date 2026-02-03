"""JSON report exporter for GaleHunTUI.

This module provides JSON export functionality for scan reports,
with custom encoding for datetime and enum types.
"""

import json
from datetime import datetime
from enum import Enum
from pathlib import Path

from galehuntui.core.exceptions import StorageError
# Avoid circular import by using string forward reference or importing inside method if needed,
# but here Report is imported from generator. Let's check generator.py imports.
# Ideally use TYPE_CHECKING
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from galehuntui.reporting.generator import Report

class ReportJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for report objects.
    
    Handles serialization of datetime, Enum, and Path objects.
    """
    
    def default(self, o):
        """Encode special types to JSON-serializable formats.
        
        Args:
            o: Object to encode
            
        Returns:
            JSON-serializable representation
        """
        if isinstance(o, datetime):
            return o.isoformat()
        
        if isinstance(o, Enum):
            return o.value
        
        if isinstance(o, Path):
            return str(o)
        
        return super().default(o)


class JSONExporter:
    """Export reports to JSON format.
    
    Provides structured JSON output suitable for programmatic consumption,
    integrations, and further processing.
    """
    
    def export(self, report: "Report", output_path: Path) -> None:
        """Export report to JSON file.
        
        Args:
            report: Report object to export
            output_path: Path where JSON file will be written
            
        Raises:
            StorageError: If export fails
        """
        try:
            # Build JSON structure
            generated_at = report.generated_at
            if hasattr(generated_at, 'isoformat'):
                generated_at_str = generated_at.isoformat()
            else:
                generated_at_str = str(generated_at)

            data = {
                "report_metadata": {
                    "generated_at": generated_at_str,
                    "generator": "GaleHunTUI",
                    "version": "1.0.0",
                },
                "scan_metadata": {
                    "run_id": report.run_metadata.id,
                    "target": report.run_metadata.target,
                    "profile": report.run_metadata.profile,
                    "engagement_mode": report.run_metadata.engagement_mode,
                    "state": report.run_metadata.state,
                    "created_at": report.run_metadata.created_at,
                    "started_at": report.run_metadata.started_at,
                    "completed_at": report.run_metadata.completed_at,
                    "duration_seconds": report.run_metadata.duration,
                    "total_steps": report.run_metadata.total_steps,
                    "completed_steps": report.run_metadata.completed_steps,
                    "failed_steps": report.run_metadata.failed_steps,
                },
                "statistics": {
                    "total_findings": report.statistics.total_findings,
                    "unique_hosts": report.statistics.unique_hosts,
                    "unique_urls": report.statistics.unique_urls,
                    "by_severity": {
                        "critical": report.statistics.critical_count,
                        "high": report.statistics.high_count,
                        "medium": report.statistics.medium_count,
                        "low": report.statistics.low_count,
                        "info": report.statistics.info_count,
                    },
                    "severity_distribution": report.statistics.severity_distribution,
                    "by_confidence": report.statistics.by_confidence,
                    "by_type": report.statistics.by_type,
                    "by_tool": report.statistics.by_tool,
                },
                "findings": [
                    {
                        "id": finding.id,
                        "type": finding.type,
                        "severity": finding.severity,
                        "confidence": finding.confidence,
                        "host": finding.host,
                        "url": finding.url,
                        "parameter": finding.parameter,
                        "tool": finding.tool,
                        "timestamp": finding.timestamp,
                        "title": finding.title,
                        "description": finding.description,
                        "reproduction_steps": finding.reproduction_steps,
                        "remediation": finding.remediation,
                        "references": finding.references,
                        "evidence_paths": finding.evidence_paths,
                    }
                    for finding in report.findings
                ],
            }
            
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write JSON with custom encoder
            with output_path.open("w", encoding="utf-8") as f:
                json.dump(
                    data,
                    f,
                    cls=ReportJSONEncoder,
                    indent=2,
                    ensure_ascii=False,
                )
            
        except (OSError, TypeError, ValueError) as e:
            raise StorageError(f"Failed to export JSON report: {e}") from e
