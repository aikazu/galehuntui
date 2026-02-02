"""URL deduplication for efficient testing.

This module provides URL deduplication functionality to eliminate redundant
URLs that would result in duplicate testing. It uses normalized URLs and
supports multiple deduplication strategies.
"""

from typing import Optional
from urllib.parse import urlparse, parse_qs

from galehuntui.classifier.normalizer import URLNormalizer


class URLDeduper:
    """Deduplicate URLs based on normalized representation.
    
    Deduplication strategies:
    1. Exact match: URLs with identical normalized form
    2. Path-only: URLs with same path (ignoring query params)
    3. Structure-based: URLs with same parameter structure
    """
    
    def __init__(
        self,
        *,
        normalizer: Optional[URLNormalizer] = None,
        strategy: str = "exact"
    ):
        """Initialize URLDeduper.
        
        Args:
            normalizer: URLNormalizer instance (creates default if None)
            strategy: Deduplication strategy ("exact", "path", "structure")
        """
        self.normalizer = normalizer or URLNormalizer()
        self.strategy = strategy
        self._validate_strategy()
    
    def _validate_strategy(self) -> None:
        """Validate deduplication strategy.
        
        Raises:
            ValueError: If strategy is invalid
        """
        valid_strategies = {"exact", "path", "structure"}
        if self.strategy not in valid_strategies:
            raise ValueError(
                f"Invalid strategy '{self.strategy}'. "
                f"Must be one of: {', '.join(sorted(valid_strategies))}"
            )
    
    def deduplicate(self, urls: list[str]) -> list[str]:
        """Deduplicate a list of URLs.
        
        Args:
            urls: List of URLs to deduplicate
            
        Returns:
            Deduplicated list of URLs (preserves first occurrence order)
        """
        if not urls:
            return []
        
        seen_keys = set()
        deduplicated = []
        
        for url in urls:
            try:
                key = self._get_dedup_key(url)
                if key not in seen_keys:
                    seen_keys.add(key)
                    deduplicated.append(url)
            except ValueError:
                # Skip invalid URLs
                continue
        
        return deduplicated
    
    def _get_dedup_key(self, url: str) -> str:
        """Get deduplication key for URL based on strategy.
        
        Args:
            url: URL to process
            
        Returns:
            Deduplication key
            
        Raises:
            ValueError: If URL is invalid
        """
        if self.strategy == "exact":
            return self._exact_key(url)
        elif self.strategy == "path":
            return self._path_key(url)
        elif self.strategy == "structure":
            return self._structure_key(url)
        
        # Should not reach here due to validation
        raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def _exact_key(self, url: str) -> str:
        """Generate exact match key (normalized URL).
        
        Args:
            url: URL to process
            
        Returns:
            Normalized URL
        """
        return self.normalizer.normalize(url)
    
    def _path_key(self, url: str) -> str:
        """Generate path-only key (scheme + host + path).
        
        Args:
            url: URL to process
            
        Returns:
            Base URL without query parameters
        """
        return self.normalizer.get_base_url(url)
    
    def _structure_key(self, url: str) -> str:
        """Generate structure-based key (path + param names).
        
        This strategy considers URLs with the same parameter structure
        as duplicates, regardless of parameter values. For example:
        - https://example.com/search?q=test&lang=en
        - https://example.com/search?q=other&lang=fr
        Would be considered duplicates.
        
        Args:
            url: URL to process
            
        Returns:
            Structure key (base_url + sorted param names)
        """
        normalized = self.normalizer.normalize(url)
        parsed = urlparse(normalized)
        
        # Get base URL
        base = self.normalizer.get_base_url(url)
        
        # Extract parameter names
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            param_names = sorted(params.keys())
            param_signature = ','.join(param_names)
            return f"{base}?[{param_signature}]"
        
        return base
    
    def get_duplicates(self, urls: list[str]) -> dict[str, list[str]]:
        """Find duplicate URL groups.
        
        Args:
            urls: List of URLs to analyze
            
        Returns:
            Dictionary mapping dedup keys to lists of duplicate URLs
        """
        duplicates: dict[str, list[str]] = {}
        
        for url in urls:
            try:
                key = self._get_dedup_key(url)
                if key not in duplicates:
                    duplicates[key] = []
                duplicates[key].append(url)
            except ValueError:
                # Skip invalid URLs
                continue
        
        # Filter to only groups with actual duplicates
        return {
            key: urls_list
            for key, urls_list in duplicates.items()
            if len(urls_list) > 1
        }
    
    def count_unique(self, urls: list[str]) -> int:
        """Count unique URLs after deduplication.
        
        Args:
            urls: List of URLs to count
            
        Returns:
            Number of unique URLs
        """
        return len(self.deduplicate(urls))
    
    def is_duplicate(self, url: str, existing_urls: set[str]) -> bool:
        """Check if URL is a duplicate of any in existing set.
        
        Args:
            url: URL to check
            existing_urls: Set of existing dedup keys
            
        Returns:
            True if URL is a duplicate, False otherwise
        """
        try:
            key = self._get_dedup_key(url)
            return key in existing_urls
        except ValueError:
            # Invalid URLs are not considered duplicates
            return False
    
    def create_dedup_set(self, urls: list[str]) -> set[str]:
        """Create a set of dedup keys for fast duplicate checking.
        
        Args:
            urls: List of URLs to process
            
        Returns:
            Set of deduplication keys
        """
        dedup_set = set()
        for url in urls:
            try:
                key = self._get_dedup_key(url)
                dedup_set.add(key)
            except ValueError:
                # Skip invalid URLs
                continue
        return dedup_set
    
    def merge_and_deduplicate(self, *url_lists: list[str]) -> list[str]:
        """Merge multiple URL lists and deduplicate.
        
        Args:
            *url_lists: Variable number of URL lists
            
        Returns:
            Merged and deduplicated URL list
        """
        merged = []
        for url_list in url_lists:
            merged.extend(url_list)
        
        return self.deduplicate(merged)
    
    def deduplicate_streaming(self, urls: list[str]) -> list[str]:
        """Deduplicate URLs with memory-efficient streaming approach.
        
        This method is useful for very large URL lists where storing
        all dedup keys might be memory-intensive.
        
        Args:
            urls: List of URLs to deduplicate
            
        Returns:
            Deduplicated list of URLs
        """
        # For now, this is the same as regular deduplicate
        # In the future, could be optimized with generators or external storage
        return self.deduplicate(urls)
