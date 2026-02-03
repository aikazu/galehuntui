"""HTML report exporter for GaleHunTUI.

This module provides HTML export functionality for scan reports using
Jinja2 templates. Generates comprehensive, styled HTML reports.
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from galehuntui.core.exceptions import StorageError
from galehuntui.reporting.generator import Report


class HTMLExporter:
    """Export reports to HTML format.
    
    Uses Jinja2 templates to generate styled, comprehensive HTML reports
    with executive summaries, statistics, and detailed findings.
    """
    
    def __init__(self):
        """Initialize HTML exporter with Jinja2 environment."""
        # Get templates directory
        templates_dir = Path(__file__).parent.parent / "templates"
        
        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        # Add custom filters
        self.env.filters['severity_badge_class'] = self._severity_badge_class
        self.env.filters['confidence_badge_class'] = self._confidence_badge_class
        self.env.filters['format_datetime'] = self._format_datetime
        self.env.filters['format_duration'] = self._format_duration
    
    def export(self, report: Report, output_path: Path) -> None:
        """Export report to HTML file.
        
        Args:
            report: Report object to export
            output_path: Path where HTML file will be written
            
        Raises:
            StorageError: If export fails
        """
        try:
            # Load template
            template = self.env.get_template('report.html.j2')
            
            # Render template with report data
            html_content = template.render(
                report=report,
                run=report.run_metadata,
                findings=report.findings,
                stats=report.statistics,
                executive_summary=report.executive_summary,
            )
            
            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write HTML file
            output_path.write_text(html_content, encoding='utf-8')
            
        except Exception as e:
            raise StorageError(f"Failed to export HTML report: {e}") from e
    
    @staticmethod
    def _severity_badge_class(severity: str) -> str:
        """Get CSS class for severity badge.
        
        Args:
            severity: Severity level
            
        Returns:
            CSS class name
        """
        severity_lower = severity.lower()
        
        if severity_lower == 'critical':
            return 'badge-critical'
        elif severity_lower == 'high':
            return 'badge-high'
        elif severity_lower == 'medium':
            return 'badge-medium'
        elif severity_lower == 'low':
            return 'badge-low'
        elif severity_lower == 'info':
            return 'badge-info'
        
        return 'badge-default'
    
    @staticmethod
    def _confidence_badge_class(confidence: str) -> str:
        """Get CSS class for confidence badge.
        
        Args:
            confidence: Confidence level
            
        Returns:
            CSS class name
        """
        confidence_lower = confidence.lower()
        
        if confidence_lower == 'confirmed':
            return 'badge-confirmed'
        elif confidence_lower == 'firm':
            return 'badge-firm'
        elif confidence_lower == 'tentative':
            return 'badge-tentative'
        
        return 'badge-default'
    
    @staticmethod
    def _format_datetime(dt) -> str:
        """Format datetime for display.
        
        Args:
            dt: Datetime object or None
            
        Returns:
            Formatted datetime string
        """
        if dt is None:
            return 'N/A'
        
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    
    @staticmethod
    def _format_duration(seconds) -> str:
        """Format duration in seconds to human-readable format.
        
        Args:
            seconds: Duration in seconds or None
            
        Returns:
            Formatted duration string
        """
        if seconds is None:
            return 'N/A'
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
