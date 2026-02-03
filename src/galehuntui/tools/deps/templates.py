"""Nuclei template management utilities."""

from pathlib import Path
from typing import Optional

from galehuntui.tools.deps.manager import DependencyManager


class TemplateManager:
    
    TEMPLATE_CATEGORIES = [
        "cves",
        "vulnerabilities", 
        "exposures",
        "misconfiguration",
        "default-logins",
        "takeovers",
        "file",
        "fuzzing",
        "miscellaneous",
        "network",
        "ssl",
        "dns",
        "headless",
        "helpers",
        "iot",
        "javascript",
        "osint",
        "cloud",
    ]
    
    def __init__(self, deps_manager: DependencyManager):
        self.deps_manager = deps_manager
        self.templates_dir = deps_manager.templates_dir
    
    def get_template_path(self) -> Optional[Path]:
        path = self.templates_dir / "nuclei-templates"
        return path if path.exists() else None
    
    def get_template_path_or_raise(self) -> Path:
        path = self.get_template_path()
        if path is None:
            raise FileNotFoundError("nuclei-templates not installed")
        return path
    
    def get_category_path(self, category: str) -> Optional[Path]:
        base = self.get_template_path()
        if base is None:
            return None
        
        category_path = base / category
        return category_path if category_path.exists() else None
    
    def list_categories(self) -> list[str]:
        base = self.get_template_path()
        if base is None:
            return []
        
        return [
            d.name for d in base.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]
    
    def get_templates_by_severity(self, severity: str) -> list[Path]:
        base = self.get_template_path()
        if base is None:
            return []
        
        results = []
        severity_lower = severity.lower()
        
        for template_file in base.rglob("*.yaml"):
            try:
                content = template_file.read_text()
                if f"severity: {severity_lower}" in content:
                    results.append(template_file)
            except (OSError, UnicodeDecodeError):
                continue
        
        return results
    
    def get_templates_by_tag(self, tag: str) -> list[Path]:
        base = self.get_template_path()
        if base is None:
            return []
        
        results = []
        tag_lower = tag.lower()
        
        for template_file in base.rglob("*.yaml"):
            try:
                content = template_file.read_text()
                if tag_lower in content.lower():
                    results.append(template_file)
            except (OSError, UnicodeDecodeError):
                continue
        
        return results
    
    def count_templates(self) -> int:
        base = self.get_template_path()
        if base is None:
            return 0
        return len(list(base.rglob("*.yaml")))
    
    def search(self, pattern: str) -> list[Path]:
        base = self.get_template_path()
        if base is None:
            return []
        return sorted(base.rglob(f"*{pattern}*.yaml"))
