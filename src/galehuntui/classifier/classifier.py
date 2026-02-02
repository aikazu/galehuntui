"""URL classification for targeted vulnerability testing.

This module provides URL classification functionality to categorize URLs
based on their injection potential. URLs are classified into groups for
targeted testing (XSS, SQLi, SSRF, etc.).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs, ParseResult

from galehuntui.core.constants import ClassificationGroup, STATIC_EXTENSIONS
from galehuntui.core.models import ClassificationResult
from galehuntui.classifier.normalizer import URLNormalizer
from galehuntui.classifier.deduper import URLDeduper


@dataclass
class ClassificationRule:
    """Rule for classifying URLs into groups.
    
    A rule consists of patterns to match against different parts of the URL
    (path, parameters, values) and assigns URLs to classification groups.
    """
    name: str
    group: ClassificationGroup
    patterns: list[str]                    # Regex patterns to match
    match_location: str = "param_name"     # Where to match: param_name, param_value, path, full_url
    confidence: float = 1.0                # Classification confidence (0.0-1.0)
    description: str = ""
    
    def __post_init__(self) -> None:
        """Compile regex patterns after initialization."""
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.patterns
        ]
    
    def matches(self, url: str, parsed_url: Optional[ParseResult] = None) -> bool:
        """Check if URL matches this rule.
        
        Args:
            url: URL to check
            parsed_url: Pre-parsed URL object (optional, for efficiency)
            
        Returns:
            True if URL matches rule, False otherwise
        """
        if parsed_url is None:
            parsed_url = urlparse(url)
        
        target_text = self._get_target_text(url, parsed_url)
        
        for pattern in self.compiled_patterns:
            if pattern.search(target_text):
                return True
        
        return False
    
    def _get_target_text(self, url: str, parsed_url: ParseResult) -> str:
        """Get text to match based on match_location.
        
        Args:
            url: Full URL
            parsed_url: Parsed URL object
            
        Returns:
            Text to match against patterns
        """
        if self.match_location == "full_url":
            return url
        elif self.match_location == "path":
            return parsed_url.path
        elif self.match_location == "param_name":
            if parsed_url.query:
                params = parse_qs(parsed_url.query, keep_blank_values=True)
                return " ".join(params.keys())
            return ""
        elif self.match_location == "param_value":
            if parsed_url.query:
                params = parse_qs(parsed_url.query, keep_blank_values=True)
                values = []
                for param_values in params.values():
                    values.extend(param_values)
                return " ".join(values)
            return ""
        
        return ""


class URLClassifier:
    """Classify URLs for targeted vulnerability testing.
    
    Classifies URLs into groups based on injection potential:
    - xss_candidates: URLs with reflected parameters, query strings
    - sqli_candidates: URLs with ID params, numeric inputs
    - redirect_candidates: URLs with URL/redirect parameters
    - ssrf_candidates: URLs with URL/host parameters, callbacks
    - generic: Other parameterized URLs for general testing
    """
    
    def __init__(
        self,
        *,
        normalizer: Optional[URLNormalizer] = None,
        deduper: Optional[URLDeduper] = None,
        custom_rules: Optional[list[ClassificationRule]] = None
    ):
        """Initialize URLClassifier.
        
        Args:
            normalizer: URLNormalizer instance (creates default if None)
            deduper: URLDeduper instance (creates default if None)
            custom_rules: Additional custom classification rules
        """
        self.normalizer = normalizer or URLNormalizer()
        self.deduper = deduper or URLDeduper()
        self.rules = self._create_default_rules()
        
        if custom_rules:
            self.rules.extend(custom_rules)
    
    def _create_default_rules(self) -> list[ClassificationRule]:
        """Create default classification rules.
        
        Returns:
            List of classification rules
        """
        rules = []
        
        # XSS candidates - Reflected parameters
        rules.append(ClassificationRule(
            name="xss_reflected_params",
            group=ClassificationGroup.XSS,
            patterns=[
                r"\b(q|query|search|keyword|term|s|text|message|msg|comment|content|data|input|name|value)\b",
                r"\b(title|subject|body|description|post|article|page|view)\b",
                r"\b(html|output|display|render|show)\b",
            ],
            match_location="param_name",
            confidence=0.9,
            description="Parameters that typically reflect user input"
        ))
        
        rules.append(ClassificationRule(
            name="xss_callback_params",
            group=ClassificationGroup.XSS,
            patterns=[
                r"\b(callback|jsonp|cb|function|fn|method)\b",
            ],
            match_location="param_name",
            confidence=0.95,
            description="JSONP callback parameters vulnerable to XSS"
        ))
        
        # SQLi candidates - Database-related parameters
        rules.append(ClassificationRule(
            name="sqli_id_params",
            group=ClassificationGroup.SQLI,
            patterns=[
                r"\b(id|uid|user_?id|item_?id|product_?id|post_?id|article_?id|page_?id)\b",
                r"\b(pid|oid|cid|gid|mid|tid|rid)\b",
                r"\b(key|code|ref|reference)\b",
            ],
            match_location="param_name",
            confidence=0.85,
            description="ID parameters often used in SQL queries"
        ))
        
        rules.append(ClassificationRule(
            name="sqli_filter_params",
            group=ClassificationGroup.SQLI,
            patterns=[
                r"\b(filter|sort|order|orderby|sortby|groupby|where)\b",
                r"\b(category|cat|type|status|state|condition)\b",
                r"\b(limit|offset|page|per_?page|start|count)\b",
            ],
            match_location="param_name",
            confidence=0.8,
            description="Filter and sorting parameters used in SQL"
        ))
        
        rules.append(ClassificationRule(
            name="sqli_numeric_values",
            group=ClassificationGroup.SQLI,
            patterns=[
                r"^\d+$",  # Pure numeric values
            ],
            match_location="param_value",
            confidence=0.7,
            description="Numeric parameter values often in SQL queries"
        ))
        
        # Open Redirect candidates
        rules.append(ClassificationRule(
            name="redirect_url_params",
            group=ClassificationGroup.REDIRECT,
            patterns=[
                r"\b(url|redirect|redir|return|returnto|return_?url|return_?to)\b",
                r"\b(goto|go|target|dest|destination|next|continue|forward)\b",
                r"\b(link|href|src|source|location|loc)\b",
            ],
            match_location="param_name",
            confidence=0.9,
            description="Parameters that control redirects"
        ))
        
        rules.append(ClassificationRule(
            name="redirect_url_values",
            group=ClassificationGroup.REDIRECT,
            patterns=[
                r"^https?://",  # URL values
                r"^//",         # Protocol-relative URLs
                r"^/\w+",       # Absolute paths
            ],
            match_location="param_value",
            confidence=0.85,
            description="URL values in parameters"
        ))
        
        # SSRF candidates
        rules.append(ClassificationRule(
            name="ssrf_url_params",
            group=ClassificationGroup.SSRF,
            patterns=[
                r"\b(url|uri|path|file|document|doc|image|img|photo|pic)\b",
                r"\b(host|server|domain|site|website|endpoint|api|service)\b",
                r"\b(webhook|callback|ping|fetch|load|download|upload|proxy)\b",
                r"\b(link|href|src|source|target|dest|destination)\b",
            ],
            match_location="param_name",
            confidence=0.85,
            description="Parameters that might fetch external resources"
        ))
        
        rules.append(ClassificationRule(
            name="ssrf_api_paths",
            group=ClassificationGroup.SSRF,
            patterns=[
                r"/api/.*/(fetch|proxy|image|file|download|upload)",
                r"/(webhook|callback|ping|health)",
            ],
            match_location="path",
            confidence=0.75,
            description="API paths that might fetch external resources"
        ))
        
        return rules
    
    def classify(self, url: str) -> ClassificationResult:
        """Classify a single URL.
        
        Args:
            url: URL to classify
            
        Returns:
            ClassificationResult with assigned groups
        """
        # Filter static extensions first
        if self._is_static_file(url):
            return ClassificationResult(url=url, groups=[], confidence=0.0)
        
        # Normalize URL
        try:
            normalized = self.normalizer.normalize(url)
        except ValueError:
            # Invalid URL
            return ClassificationResult(url=url, groups=[], confidence=0.0)
        
        # Parse URL once for efficiency
        parsed = urlparse(normalized)
        
        # Check if URL has parameters (required for most classifications)
        has_params = bool(parsed.query)
        
        # Apply classification rules
        matched_groups = set()
        max_confidence = 0.0
        
        for rule in self.rules:
            if rule.matches(normalized, parsed):
                matched_groups.add(rule.group.value)
                max_confidence = max(max_confidence, rule.confidence)
        
        # If URL has parameters but no specific classification, mark as generic
        if has_params and not matched_groups:
            matched_groups.add(ClassificationGroup.GENERIC.value)
            max_confidence = 0.5
        
        return ClassificationResult(
            url=url,  # Return original URL, not normalized
            groups=sorted(matched_groups),
            confidence=max_confidence
        )
    
    def classify_batch(self, urls: list[str]) -> list[ClassificationResult]:
        """Classify a batch of URLs.
        
        Args:
            urls: List of URLs to classify
            
        Returns:
            List of ClassificationResult objects
        """
        return [self.classify(url) for url in urls]
    
    def classify_and_group(self, urls: list[str]) -> dict[str, list[str]]:
        """Classify URLs and group by classification.
        
        Args:
            urls: List of URLs to classify
            
        Returns:
            Dictionary mapping group names to lists of URLs
        """
        groups: dict[str, list[str]] = {
            ClassificationGroup.XSS.value: [],
            ClassificationGroup.SQLI.value: [],
            ClassificationGroup.REDIRECT.value: [],
            ClassificationGroup.SSRF.value: [],
            ClassificationGroup.GENERIC.value: [],
        }
        
        for url in urls:
            result = self.classify(url)
            
            # Skip URLs with no classification
            if not result.groups:
                continue
            
            # Add URL to all matching groups
            for group in result.groups:
                if group in groups:
                    groups[group].append(url)
        
        return groups
    
    def classify_deduplicate_and_group(
        self,
        urls: list[str],
        *,
        deduplicate_per_group: bool = True
    ) -> dict[str, list[str]]:
        """Classify URLs, deduplicate, and group.
        
        This is the recommended method for processing crawled URLs before
        targeted testing. It combines classification and deduplication.
        
        Args:
            urls: List of URLs to process
            deduplicate_per_group: Whether to deduplicate within each group
            
        Returns:
            Dictionary mapping group names to deduplicated lists of URLs
        """
        # First deduplicate input URLs
        deduplicated = self.deduper.deduplicate(urls)
        
        # Classify and group
        groups = self.classify_and_group(deduplicated)
        
        # Optionally deduplicate within each group
        if deduplicate_per_group:
            for group_name in groups:
                groups[group_name] = self.deduper.deduplicate(groups[group_name])
        
        return groups
    
    def _is_static_file(self, url: str) -> bool:
        """Check if URL points to a static file.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL has a static file extension, False otherwise
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            # Get file extension
            path_obj = Path(path)
            ext = path_obj.suffix
            
            return ext in STATIC_EXTENSIONS
        except Exception:
            return False
    
    def filter_static_files(self, urls: list[str]) -> list[str]:
        """Filter out URLs pointing to static files.
        
        Args:
            urls: List of URLs to filter
            
        Returns:
            List of URLs without static file extensions
        """
        return [url for url in urls if not self._is_static_file(url)]
    
    def add_rule(self, rule: ClassificationRule) -> None:
        """Add a custom classification rule.
        
        Args:
            rule: ClassificationRule to add
        """
        self.rules.append(rule)
    
    def get_statistics(self, urls: list[str]) -> dict[str, int]:
        """Get classification statistics for a list of URLs.
        
        Args:
            urls: List of URLs to analyze
            
        Returns:
            Dictionary with classification statistics
        """
        groups = self.classify_and_group(urls)
        
        stats = {
            "total_urls": len(urls),
            "static_files": sum(1 for url in urls if self._is_static_file(url)),
            "classified_urls": sum(len(group_urls) for group_urls in groups.values()),
        }
        
        # Add per-group counts
        for group_name, group_urls in groups.items():
            stats[f"{group_name}_count"] = len(group_urls)
        
        return stats
