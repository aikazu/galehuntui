"""Unit tests for URL normalizer module.

Tests for URLNormalizer including scheme normalization, port handling,
path normalization, query parameter sorting, and fragment removal.
"""

import sys
import unittest
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from galehuntui.classifier.normalizer import URLNormalizer


class TestURLNormalizer(unittest.TestCase):
    """Test suite for URLNormalizer class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.normalizer = URLNormalizer()
    
    def test_normalize_adds_scheme(self):
        """Test that URLs without scheme get http:// added."""
        result = self.normalizer.normalize("example.com")
        self.assertTrue(result.startswith("http://"))
        self.assertIn("example.com", result)
    
    def test_normalize_lowercase_scheme(self):
        """Test that scheme is converted to lowercase."""
        result = self.normalizer.normalize("HTTP://example.com")
        self.assertTrue(result.startswith("http://"))
    
    def test_normalize_lowercase_host(self):
        """Test that host is converted to lowercase."""
        result = self.normalizer.normalize("http://Example.COM")
        self.assertIn("example.com", result)
    
    def test_normalize_removes_trailing_slash(self):
        """Test that trailing slashes are removed from paths (except root)."""
        result = self.normalizer.normalize("http://example.com/path/")
        self.assertEqual(result, "http://example.com/path")
        
        # Root path should keep trailing slash
        result_root = self.normalizer.normalize("http://example.com/")
        self.assertEqual(result_root, "http://example.com/")
    
    def test_normalize_sorts_query_params(self):
        """Test that query parameters are sorted alphabetically."""
        result = self.normalizer.normalize("http://example.com?b=2&a=1")
        self.assertIn("a=1&b=2", result)
    
    def test_normalize_removes_default_http_port(self):
        """Test that default HTTP port (80) is removed."""
        result = self.normalizer.normalize("http://example.com:80/path")
        self.assertEqual(result, "http://example.com/path")
    
    def test_normalize_removes_default_https_port(self):
        """Test that default HTTPS port (443) is removed."""
        result = self.normalizer.normalize("https://example.com:443/path")
        self.assertEqual(result, "https://example.com/path")
    
    def test_normalize_keeps_non_default_port(self):
        """Test that non-default ports are preserved."""
        result = self.normalizer.normalize("http://example.com:8080/path")
        self.assertIn(":8080", result)
    
    def test_normalize_removes_fragment_by_default(self):
        """Test that URL fragments are removed by default."""
        result = self.normalizer.normalize("http://example.com/path#section")
        self.assertNotIn("#section", result)
        self.assertEqual(result, "http://example.com/path")
    
    def test_normalize_keeps_fragment_when_configured(self):
        """Test that fragments can be preserved when configured."""
        normalizer = URLNormalizer(remove_fragments=False)
        result = normalizer.normalize("http://example.com/path#section")
        self.assertIn("#section", result)
    
    def test_normalize_handles_path_dots(self):
        """Test that . and .. in paths are resolved."""
        result = self.normalizer.normalize("http://example.com/a/b/../c/./d")
        self.assertEqual(result, "http://example.com/a/c/d")
    
    def test_normalize_adds_leading_slash_to_path(self):
        """Test that paths get leading slash if missing."""
        result = self.normalizer.normalize("http://example.com/path")
        parsed_path = result.split("example.com")[1]
        self.assertTrue(parsed_path.startswith("/"))
    
    def test_normalize_empty_path_becomes_root(self):
        """Test that empty path becomes /."""
        result = self.normalizer.normalize("http://example.com")
        self.assertTrue(result.endswith("/"))
    
    def test_normalize_complex_url(self):
        """Test normalization of complex URL with multiple features."""
        url = "HTTP://Example.COM:80/path/../page/?z=3&a=1#section"
        result = self.normalizer.normalize(url)
        
        self.assertEqual(result, "http://example.com/page?a=1&z=3")
    
    def test_normalize_raises_on_invalid_url(self):
        """Test that invalid URLs raise ValueError."""
        with self.assertRaises(ValueError):
            self.normalizer.normalize("")
        
        with self.assertRaises(ValueError):
            self.normalizer.normalize(None)
    
    def test_normalize_handles_query_without_sorting(self):
        """Test that query params can be preserved unsorted."""
        normalizer = URLNormalizer(sort_params=False)
        result = normalizer.normalize("http://example.com?b=2&a=1")
        # Order may vary due to parse_qs behavior, but both should be present
        self.assertIn("a=1", result)
        self.assertIn("b=2", result)
    
    def test_normalize_batch_processes_multiple_urls(self):
        """Test that normalize_batch processes multiple URLs."""
        urls = [
            "HTTP://Example.COM/path/",
            "http://example.com?b=2&a=1",
            "https://test.com:443/page",
        ]
        
        results = self.normalizer.normalize_batch(urls)
        
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0], "http://example.com/path")
        self.assertIn("a=1&b=2", results[1])
        self.assertEqual(results[2], "https://test.com/page")
    
    def test_normalize_batch_skips_invalid_urls(self):
        """Test that normalize_batch skips invalid URLs without failing."""
        urls = [
            "http://valid.com",
            "",
            None,
            "http://another-valid.com",
        ]
        
        results = self.normalizer.normalize_batch(urls)
        
        # Should only have 2 valid results
        self.assertEqual(len(results), 2)
    
    def test_get_base_url_removes_query_and_fragment(self):
        """Test that get_base_url returns URL without query or fragment."""
        url = "http://example.com/path?query=1#fragment"
        result = self.normalizer.get_base_url(url)
        
        self.assertEqual(result, "http://example.com/path")
        self.assertNotIn("?", result)
        self.assertNotIn("#", result)
    
    def test_get_domain_extracts_host(self):
        """Test that get_domain extracts the domain name."""
        url = "http://example.com:8080/path?query=1"
        result = self.normalizer.get_domain(url)
        
        self.assertEqual(result, "example.com")
    
    def test_get_domain_lowercase(self):
        """Test that get_domain returns lowercase domain."""
        url = "http://Example.COM/path"
        result = self.normalizer.get_domain(url)
        
        self.assertEqual(result, "example.com")
    
    def test_get_domain_removes_port(self):
        """Test that get_domain removes port number."""
        url = "http://example.com:8080/path"
        result = self.normalizer.get_domain(url)
        
        self.assertEqual(result, "example.com")
        self.assertNotIn(":", result)
    
    def test_get_domain_returns_none_for_invalid_url(self):
        """Test that get_domain returns None for invalid URLs."""
        result = self.normalizer.get_domain("not-a-valid-url")
        self.assertIsNone(result)
    
    def test_normalize_handles_multiple_query_values(self):
        """Test normalization of query params with multiple values."""
        url = "http://example.com?a=1&a=2&b=3"
        result = self.normalizer.normalize(url)
        
        # Should preserve both values of 'a'
        self.assertIn("a=1", result)
        self.assertIn("a=2", result)
        self.assertIn("b=3", result)
    
    def test_normalize_handles_empty_query_values(self):
        """Test normalization of query params with empty values."""
        url = "http://example.com?empty=&nonempty=value"
        result = self.normalizer.normalize(url)
        
        # Both params should be present
        self.assertIn("empty=", result)
        self.assertIn("nonempty=value", result)
    
    def test_normalize_handles_subdomains(self):
        """Test normalization of URLs with subdomains."""
        url = "http://sub.domain.example.com/path"
        result = self.normalizer.normalize(url)
        
        self.assertIn("sub.domain.example.com", result)
    
    def test_normalize_handles_ipv4_addresses(self):
        """Test normalization of URLs with IPv4 addresses."""
        url = "http://192.168.1.1:8080/path"
        result = self.normalizer.normalize(url)
        
        self.assertIn("192.168.1.1", result)
        self.assertIn(":8080", result)


class TestURLNormalizerEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions for URLNormalizer."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.normalizer = URLNormalizer()
    
    def test_normalize_url_with_username_password(self):
        """Test normalization preserves authentication credentials."""
        url = "http://user:pass@example.com/path"
        result = self.normalizer.normalize(url)
        
        self.assertIn("user:pass@", result)
    
    def test_normalize_url_with_international_domain(self):
        """Test normalization of internationalized domain names."""
        # This tests that the normalizer doesn't break on unicode domains
        url = "http://例え.jp/path"
        try:
            result = self.normalizer.normalize(url)
            self.assertIn("jp", result)
        except ValueError:
            # If it raises ValueError, that's acceptable for this implementation
            pass
    
    def test_normalize_preserves_special_characters_in_query(self):
        """Test that special characters in query are handled properly."""
        url = "http://example.com?search=hello+world&filter=a%20b"
        result = self.normalizer.normalize(url)
        
        # Should have both params
        self.assertIn("search=", result)
        self.assertIn("filter=", result)
    
    def test_get_base_url_with_empty_path(self):
        """Test get_base_url with URL that has no path."""
        url = "http://example.com?query=1"
        result = self.normalizer.get_base_url(url)
        
        self.assertEqual(result, "http://example.com/")
    
    def test_normalize_batch_with_empty_list(self):
        """Test normalize_batch with empty input list."""
        results = self.normalizer.normalize_batch([])
        
        self.assertEqual(results, [])
        self.assertIsInstance(results, list)


if __name__ == "__main__":
    unittest.main()
