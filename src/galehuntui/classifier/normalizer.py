"""URL normalization for deduplication and classification.

This module provides URL normalization functionality to ensure consistent
URL representation before deduplication and classification. It handles:
- Protocol normalization
- Default port removal
- Path normalization
- Query parameter sorting
- Fragment removal
"""

from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from typing import Optional


class URLNormalizer:
    """Normalize URLs for consistent representation.
    
    Normalization steps:
    1. Convert scheme and host to lowercase
    2. Remove default ports (80 for HTTP, 443 for HTTPS)
    3. Remove trailing slashes from paths (except root)
    4. Sort query parameters alphabetically
    5. Remove fragments
    6. Decode unnecessary percent-encoding
    7. Normalize path (remove . and ..)
    """
    
    DEFAULT_PORTS = {
        'http': 80,
        'https': 443,
    }
    
    def __init__(self, *, sort_params: bool = True, remove_fragments: bool = True):
        """Initialize URLNormalizer.
        
        Args:
            sort_params: Whether to sort query parameters alphabetically
            remove_fragments: Whether to remove URL fragments (#...)
        """
        self.sort_params = sort_params
        self.remove_fragments = remove_fragments
    
    def normalize(self, url: str) -> str:
        """Normalize a single URL.
        
        Args:
            url: URL to normalize
            
        Returns:
            Normalized URL string
            
        Raises:
            ValueError: If URL is invalid or cannot be parsed
        """
        if not url or not isinstance(url, str):
            raise ValueError(f"Invalid URL: {url}")
        
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Failed to parse URL '{url}': {e}")
        
        # Normalize scheme and host
        scheme = parsed.scheme.lower() if parsed.scheme else 'http'
        netloc = self._normalize_netloc(parsed.netloc, scheme)
        
        # Normalize path
        path = self._normalize_path(parsed.path)
        
        # Normalize query
        query = self._normalize_query(parsed.query) if parsed.query else ''
        
        # Handle fragment
        fragment = '' if self.remove_fragments else parsed.fragment
        
        # Reconstruct URL
        normalized = urlunparse((
            scheme,
            netloc,
            path,
            '',  # params (deprecated, always empty)
            query,
            fragment
        ))
        
        return normalized
    
    def normalize_batch(self, urls: list[str]) -> list[str]:
        """Normalize a batch of URLs.
        
        Args:
            urls: List of URLs to normalize
            
        Returns:
            List of normalized URLs (invalid URLs are skipped)
        """
        normalized = []
        for url in urls:
            try:
                normalized.append(self.normalize(url))
            except ValueError:
                # Skip invalid URLs
                continue
        return normalized
    
    def _normalize_netloc(self, netloc: str, scheme: str) -> str:
        """Normalize network location (host:port).
        
        Args:
            netloc: Network location string
            scheme: URL scheme
            
        Returns:
            Normalized netloc
        """
        if not netloc:
            return netloc
        
        # Convert to lowercase
        netloc = netloc.lower()
        
        # Remove default ports
        if ':' in netloc:
            host, port_str = netloc.rsplit(':', 1)
            try:
                port = int(port_str)
                default_port = self.DEFAULT_PORTS.get(scheme)
                if port == default_port:
                    netloc = host
            except ValueError:
                # Port is not a number, keep as is
                pass
        
        return netloc
    
    def _normalize_path(self, path: str) -> str:
        """Normalize URL path.
        
        Args:
            path: URL path
            
        Returns:
            Normalized path
        """
        if not path:
            return '/'
        
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path
        
        # Remove trailing slash (except for root)
        if len(path) > 1 and path.endswith('/'):
            path = path.rstrip('/')
        
        # Normalize . and .. in path
        path = self._resolve_path_segments(path)
        
        return path
    
    def _resolve_path_segments(self, path: str) -> str:
        """Resolve . and .. segments in path.
        
        Args:
            path: URL path
            
        Returns:
            Resolved path
        """
        segments = path.split('/')
        resolved = []
        
        for segment in segments:
            if segment == '..':
                if resolved and resolved[-1] != '..':
                    resolved.pop()
            elif segment and segment != '.':
                resolved.append(segment)
        
        result = '/' + '/'.join(resolved)
        return result if result else '/'
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query string.
        
        Args:
            query: Query string
            
        Returns:
            Normalized query string
        """
        if not query:
            return ''
        
        # Parse query parameters
        params = parse_qs(query, keep_blank_values=True)
        
        # Sort parameters if enabled
        if self.sort_params:
            sorted_params = sorted(params.items())
        else:
            sorted_params = list(params.items())
        
        # Reconstruct query string
        # Note: parse_qs returns lists, so we take the first value
        query_parts = []
        for key, values in sorted_params:
            for value in values:
                query_parts.append(f"{key}={value}")
        
        return '&'.join(query_parts)
    
    def get_base_url(self, url: str) -> str:
        """Extract base URL (scheme + netloc + path, no query/fragment).
        
        Args:
            url: URL to process
            
        Returns:
            Base URL without query or fragment
        """
        normalized = self.normalize(url)
        parsed = urlparse(normalized)
        
        base = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            '',
            '',
            ''
        ))
        
        return base
    
    def get_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL.
        
        Args:
            url: URL to process
            
        Returns:
            Domain name (host without port) or None if invalid
        """
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            
            # Remove port if present
            if ':' in netloc:
                netloc = netloc.split(':')[0]
            
            return netloc if netloc else None
        except Exception:
            return None
