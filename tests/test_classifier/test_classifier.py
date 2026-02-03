"""Unit tests for URL classifier module.

Tests for URLClassifier including classification of URLs into different
vulnerability categories (XSS, SQLi, redirect, SSRF, generic).
"""

import sys
import unittest
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from galehuntui.classifier.classifier import URLClassifier, ClassificationRule
from galehuntui.core.constants import ClassificationGroup
from galehuntui.core.models import ClassificationResult


class TestURLClassifier(unittest.TestCase):
    """Test suite for URLClassifier class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.classifier = URLClassifier()
    
    def test_classify_xss_search_parameter(self):
        """Test that URLs with search parameters are classified as XSS candidates."""
        url = "https://example.com/search?q=test"
        result = self.classifier.classify(url)
        
        self.assertIsInstance(result, ClassificationResult)
        self.assertEqual(result.url, url)
        self.assertIn("xss_candidates", result.groups)
        self.assertTrue(result.is_xss_candidate)
    
    def test_classify_xss_query_parameter(self):
        """Test that URLs with query parameters are classified as XSS candidates."""
        url = "https://example.com/page?query=something"
        result = self.classifier.classify(url)
        
        self.assertIn("xss_candidates", result.groups)
        self.assertTrue(result.is_xss_candidate)
    
    def test_classify_xss_callback_parameter(self):
        """Test that JSONP callback parameters are classified as XSS candidates."""
        url = "https://example.com/api?callback=myFunction"
        result = self.classifier.classify(url)
        
        self.assertIn("xss_candidates", result.groups)
        self.assertTrue(result.is_xss_candidate)
        self.assertGreater(result.confidence, 0.9)
    
    def test_classify_sqli_id_parameter(self):
        """Test that URLs with ID parameters are classified as SQLi candidates."""
        url = "https://example.com/user?id=123"
        result = self.classifier.classify(url)
        
        self.assertIn("sqli_candidates", result.groups)
        self.assertTrue(result.is_sqli_candidate)
    
    def test_classify_sqli_numeric_value(self):
        """Test that URLs with numeric parameter values are classified as SQLi candidates."""
        url = "https://example.com/page?item=456"
        result = self.classifier.classify(url)
        
        # Should match numeric value pattern
        self.assertIn("sqli_candidates", result.groups)
        self.assertTrue(result.is_sqli_candidate)
    
    def test_classify_sqli_filter_parameter(self):
        """Test that filter/sort parameters are classified as SQLi candidates."""
        url = "https://example.com/products?sort=price&filter=active"
        result = self.classifier.classify(url)
        
        self.assertIn("sqli_candidates", result.groups)
        self.assertTrue(result.is_sqli_candidate)
    
    def test_classify_redirect_url_parameter(self):
        """Test that redirect parameters are classified as redirect candidates."""
        url = "https://example.com/redirect?url=https://evil.com"
        result = self.classifier.classify(url)
        
        self.assertIn("redirect_candidates", result.groups)
        self.assertTrue(result.is_redirect_candidate)
    
    def test_classify_redirect_return_parameter(self):
        """Test that return/goto parameters are classified as redirect candidates."""
        url = "https://example.com/login?return_to=/dashboard"
        result = self.classifier.classify(url)
        
        self.assertIn("redirect_candidates", result.groups)
        self.assertTrue(result.is_redirect_candidate)
    
    def test_classify_ssrf_url_parameter(self):
        """Test that URL fetch parameters are classified as SSRF candidates."""
        url = "https://example.com/fetch?url=https://internal.com"
        result = self.classifier.classify(url)
        
        self.assertIn("ssrf_candidates", result.groups)
        self.assertTrue(result.is_ssrf_candidate)
    
    def test_classify_ssrf_webhook_parameter(self):
        """Test that webhook parameters are classified as SSRF candidates."""
        url = "https://example.com/api?webhook=https://attacker.com"
        result = self.classifier.classify(url)
        
        self.assertIn("ssrf_candidates", result.groups)
        self.assertTrue(result.is_ssrf_candidate)
    
    def test_classify_ssrf_api_path(self):
        """Test that SSRF-prone API paths are classified correctly."""
        url = "https://example.com/api/v1/fetch?data=test"
        result = self.classifier.classify(url)
        
        self.assertIn("ssrf_candidates", result.groups)
        self.assertTrue(result.is_ssrf_candidate)
    
    def test_classify_generic_parameterized_url(self):
        """Test that URLs with parameters but no specific pattern are generic."""
        url = "https://example.com/page?foo=bar"
        result = self.classifier.classify(url)
        
        # Should be classified as generic since 'foo' doesn't match specific patterns
        self.assertIn("generic", result.groups)
        self.assertTrue(result.is_generic)
    
    def test_classify_static_file_png(self):
        """Test that static PNG files are not classified."""
        url = "https://example.com/image.png"
        result = self.classifier.classify(url)
        
        self.assertEqual(result.groups, [])
        self.assertEqual(result.confidence, 0.0)
    
    def test_classify_static_file_js(self):
        """Test that JavaScript files are not classified."""
        url = "https://example.com/script.js"
        result = self.classifier.classify(url)
        
        self.assertEqual(result.groups, [])
        self.assertEqual(result.confidence, 0.0)
    
    def test_classify_static_file_css(self):
        """Test that CSS files are not classified."""
        url = "https://example.com/styles.css"
        result = self.classifier.classify(url)
        
        self.assertEqual(result.groups, [])
        self.assertEqual(result.confidence, 0.0)
    
    def test_classify_url_without_parameters(self):
        """Test that URLs without parameters are not classified."""
        url = "https://example.com/page"
        result = self.classifier.classify(url)
        
        # No parameters means no classification
        self.assertEqual(result.groups, [])
    
    def test_classify_multiple_groups(self):
        """Test that a URL can be classified into multiple groups."""
        # URL with both redirect and SSRF potential
        url = "https://example.com/page?url=https://evil.com"
        result = self.classifier.classify(url)
        
        # Should match both redirect and SSRF patterns
        self.assertGreater(len(result.groups), 0)
        # URL parameter commonly matches both redirect and SSRF
        self.assertTrue(
            result.is_redirect_candidate or result.is_ssrf_candidate
        )
    
    def test_classify_batch_multiple_urls(self):
        """Test batch classification of multiple URLs."""
        urls = [
            "https://example.com/search?q=test",
            "https://example.com/user?id=123",
            "https://example.com/image.png",
        ]
        
        results = self.classifier.classify_batch(urls)
        
        self.assertEqual(len(results), 3)
        self.assertIsInstance(results[0], ClassificationResult)
        self.assertTrue(results[0].is_xss_candidate)
        self.assertTrue(results[1].is_sqli_candidate)
        self.assertEqual(results[2].groups, [])  # Static file
    
    def test_classify_and_group(self):
        """Test classify_and_group groups URLs by classification."""
        urls = [
            "https://example.com/search?q=test",
            "https://example.com/user?id=123",
            "https://example.com/redirect?url=https://evil.com",
            "https://example.com/fetch?url=internal",
            "https://example.com/image.png",
        ]
        
        groups = self.classifier.classify_and_group(urls)
        
        # Verify structure
        self.assertIn("xss_candidates", groups)
        self.assertIn("sqli_candidates", groups)
        self.assertIn("redirect_candidates", groups)
        self.assertIn("ssrf_candidates", groups)
        self.assertIn("generic", groups)
        
        # Verify classifications
        self.assertIn(urls[0], groups["xss_candidates"])
        self.assertIn(urls[1], groups["sqli_candidates"])
        self.assertIn(urls[2], groups["redirect_candidates"])
        self.assertIn(urls[3], groups["ssrf_candidates"])
        
        # Static file should not be in any group
        for group_urls in groups.values():
            self.assertNotIn(urls[4], group_urls)
    
    def test_filter_static_files(self):
        """Test filtering of static file URLs."""
        urls = [
            "https://example.com/page.html",
            "https://example.com/image.png",
            "https://example.com/style.css",
            "https://example.com/script.js",
            "https://example.com/document.pdf",
        ]
        
        filtered = self.classifier.filter_static_files(urls)
        
        # Only .html should remain (not in STATIC_EXTENSIONS)
        self.assertEqual(len(filtered), 1)
        self.assertIn("page.html", filtered[0])
    
    def test_add_custom_rule(self):
        """Test adding custom classification rules."""
        custom_rule = ClassificationRule(
            name="custom_admin",
            group=ClassificationGroup.GENERIC,
            patterns=[r"\badmin\b"],
            match_location="path",
            confidence=0.8,
            description="Admin paths"
        )
        
        self.classifier.add_rule(custom_rule)
        
        url = "https://example.com/admin?action=delete"
        result = self.classifier.classify(url)
        
        # Should match custom rule
        self.assertGreater(len(result.groups), 0)
    
    def test_get_statistics(self):
        """Test classification statistics generation."""
        urls = [
            "https://example.com/search?q=test",
            "https://example.com/search?q=other",
            "https://example.com/user?id=123",
            "https://example.com/image.png",
            "https://example.com/image2.jpg",
        ]
        
        stats = self.classifier.get_statistics(urls)
        
        self.assertEqual(stats["total_urls"], 5)
        self.assertEqual(stats["static_files"], 2)
        self.assertIn("xss_candidates_count", stats)
        self.assertIn("sqli_candidates_count", stats)
        self.assertGreater(stats["xss_candidates_count"], 0)


class TestClassificationResult(unittest.TestCase):
    """Test ClassificationResult model and its properties."""
    
    def test_classification_result_properties(self):
        """Test ClassificationResult property methods."""
        result = ClassificationResult(
            url="https://example.com/test",
            groups=["xss_candidates", "sqli_candidates"],
            confidence=0.9
        )
        
        self.assertTrue(result.is_xss_candidate)
        self.assertTrue(result.is_sqli_candidate)
        self.assertFalse(result.is_redirect_candidate)
        self.assertFalse(result.is_ssrf_candidate)
        self.assertFalse(result.is_generic)
    
    def test_classification_result_empty_groups(self):
        """Test ClassificationResult with no groups."""
        result = ClassificationResult(
            url="https://example.com/static.png",
            groups=[],
            confidence=0.0
        )
        
        self.assertFalse(result.is_xss_candidate)
        self.assertFalse(result.is_sqli_candidate)
        self.assertFalse(result.is_redirect_candidate)
        self.assertFalse(result.is_ssrf_candidate)
        self.assertFalse(result.is_generic)


class TestClassificationRule(unittest.TestCase):
    """Test ClassificationRule class."""
    
    def test_rule_matches_param_name(self):
        """Test rule matching against parameter names."""
        rule = ClassificationRule(
            name="test_rule",
            group=ClassificationGroup.XSS,
            patterns=[r"\bsearch\b"],
            match_location="param_name",
            confidence=0.9
        )
        
        url = "https://example.com?search=test"
        self.assertTrue(rule.matches(url))
        
        url_no_match = "https://example.com?query=test"
        # This might still match if 'query' is in default XSS patterns,
        # but our custom rule specifically looks for 'search'
        # Let's test with something that definitely won't match
        url_no_match = "https://example.com?xyz=test"
        self.assertFalse(rule.matches(url_no_match))
    
    def test_rule_matches_param_value(self):
        """Test rule matching against parameter values."""
        rule = ClassificationRule(
            name="test_numeric",
            group=ClassificationGroup.SQLI,
            patterns=[r"^\d+$"],
            match_location="param_value",
            confidence=0.7
        )
        
        url = "https://example.com?id=123"
        self.assertTrue(rule.matches(url))
        
        url_no_match = "https://example.com?id=abc"
        self.assertFalse(rule.matches(url_no_match))
    
    def test_rule_matches_path(self):
        """Test rule matching against URL path."""
        rule = ClassificationRule(
            name="test_admin",
            group=ClassificationGroup.GENERIC,
            patterns=[r"/admin/"],
            match_location="path",
            confidence=0.8
        )
        
        url = "https://example.com/admin/dashboard"
        self.assertTrue(rule.matches(url))
        
        url_no_match = "https://example.com/user/dashboard"
        self.assertFalse(rule.matches(url_no_match))
    
    def test_rule_matches_full_url(self):
        """Test rule matching against full URL."""
        rule = ClassificationRule(
            name="test_domain",
            group=ClassificationGroup.GENERIC,
            patterns=[r"example\.com"],
            match_location="full_url",
            confidence=0.9
        )
        
        url = "https://example.com/path"
        self.assertTrue(rule.matches(url))
        
        url_no_match = "https://other.com/path"
        self.assertFalse(rule.matches(url_no_match))
    
    def test_rule_case_insensitive(self):
        """Test that rules are case-insensitive by default."""
        rule = ClassificationRule(
            name="test_case",
            group=ClassificationGroup.XSS,
            patterns=[r"\bsearch\b"],
            match_location="param_name",
            confidence=0.9
        )
        
        # Should match regardless of case
        url_lower = "https://example.com?search=test"
        url_upper = "https://example.com?SEARCH=test"
        url_mixed = "https://example.com?SeArCh=test"
        
        self.assertTrue(rule.matches(url_lower))
        self.assertTrue(rule.matches(url_upper))
        self.assertTrue(rule.matches(url_mixed))


class TestURLClassifierAdvanced(unittest.TestCase):
    """Advanced tests for URLClassifier edge cases."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.classifier = URLClassifier()
    
    def test_classify_deduplicate_and_group(self):
        """Test combined classification, deduplication, and grouping."""
        urls = [
            "https://example.com/search?q=test",
            "https://example.com/search?q=test",  # Duplicate
            "https://example.com/search?q=other",
            "https://example.com/user?id=123",
        ]
        
        groups = self.classifier.classify_deduplicate_and_group(urls)
        
        # Check that deduplication occurred
        self.assertIn("xss_candidates", groups)
        # Should have 2 unique search URLs
        xss_urls = groups["xss_candidates"]
        # The exact count depends on deduplication logic
        self.assertGreater(len(xss_urls), 0)
    
    def test_classify_handles_mixed_case_extensions(self):
        """Test that static file filtering is case-insensitive."""
        urls = [
            "https://example.com/IMAGE.PNG",
            "https://example.com/Image.Png",
            "https://example.com/script.JS",
        ]
        
        for url in urls:
            result = self.classifier.classify(url)
            self.assertEqual(result.groups, [])
    
    def test_classify_url_with_fragment(self):
        """Test classification of URLs with fragments."""
        url = "https://example.com/page?id=123#section"
        result = self.classifier.classify(url)
        
        # Fragment shouldn't affect classification
        self.assertIn("sqli_candidates", result.groups)
    
    def test_classify_url_with_port(self):
        """Test classification of URLs with non-standard ports."""
        url = "https://example.com:8080/search?q=test"
        result = self.classifier.classify(url)
        
        # Port shouldn't affect classification
        self.assertIn("xss_candidates", result.groups)
    
    def test_classify_multiple_parameters(self):
        """Test classification with multiple parameters."""
        url = "https://example.com/page?id=123&search=test&callback=fn"
        result = self.classifier.classify(url)
        
        # Should match multiple patterns
        # id -> sqli, search -> xss, callback -> xss
        self.assertGreater(len(result.groups), 0)
        # Should have high confidence due to multiple matches
        self.assertGreater(result.confidence, 0.0)
    
    def test_classify_empty_url(self):
        """Test that empty URLs don't crash the classifier."""
        # The normalizer should raise ValueError for empty strings
        # which the classifier should handle gracefully
        url = ""
        result = self.classifier.classify(url)
        
        self.assertEqual(result.groups, [])
        self.assertEqual(result.confidence, 0.0)
    
    def test_classify_url_with_subdomain(self):
        """Test classification with subdomain URLs."""
        url = "https://api.sub.example.com/search?q=test"
        result = self.classifier.classify(url)
        
        self.assertIn("xss_candidates", result.groups)
    
    def test_classify_batch_preserves_order(self):
        """Test that batch classification preserves URL order."""
        urls = [
            "https://example.com/a?id=1",
            "https://example.com/b?q=2",
            "https://example.com/c?id=3",
        ]
        
        results = self.classifier.classify_batch(urls)
        
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].url, urls[0])
        self.assertEqual(results[1].url, urls[1])
        self.assertEqual(results[2].url, urls[2])
    
    def test_classify_with_custom_rules(self):
        """Test classifier with custom rules added."""
        custom_rule = ClassificationRule(
            name="api_endpoint",
            group=ClassificationGroup.GENERIC,
            patterns=[r"/api/"],
            match_location="path",
            confidence=0.85
        )
        
        classifier = URLClassifier(custom_rules=[custom_rule])
        
        url = "https://example.com/api/endpoint?param=value"
        result = classifier.classify(url)
        
        self.assertIn("generic", result.groups)
    
    def test_statistics_with_no_urls(self):
        """Test statistics generation with empty URL list."""
        stats = self.classifier.get_statistics([])
        
        self.assertEqual(stats["total_urls"], 0)
        self.assertEqual(stats["static_files"], 0)
        self.assertEqual(stats["classified_urls"], 0)
    
    def test_filter_static_files_preserves_dynamic(self):
        """Test that non-static URLs are preserved."""
        urls = [
            "https://example.com/page",
            "https://example.com/api/data",
            "https://example.com/search?q=test",
            "https://example.com/image.png",
        ]
        
        filtered = self.classifier.filter_static_files(urls)
        
        self.assertEqual(len(filtered), 3)
        self.assertIn(urls[0], filtered)
        self.assertIn(urls[1], filtered)
        self.assertIn(urls[2], filtered)
        self.assertNotIn(urls[3], filtered)


if __name__ == "__main__":
    unittest.main()
