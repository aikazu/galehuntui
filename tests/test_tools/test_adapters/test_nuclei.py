"""Unit tests for NucleiAdapter.

Tests command building, output parsing, severity mapping, and confidence
determination without requiring the actual nuclei binary.
"""

import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from galehuntui.core.models import (
    ToolConfig,
    Severity,
    Confidence,
)
from galehuntui.tools.adapters.nuclei import NucleiAdapter


class TestNucleiAdapter(unittest.IsolatedAsyncioTestCase):
    """Test cases for NucleiAdapter."""

    def setUp(self):
        """Set up test fixtures."""
        self.bin_path = Path("/mock/tools/bin")
        self.adapter = NucleiAdapter(self.bin_path)

    def test_adapter_attributes(self):
        """Test adapter has correct attributes."""
        self.assertEqual(self.adapter.name, "nuclei")
        self.assertTrue(self.adapter.required)
        self.assertIsNone(self.adapter.mode_required)

    def test_build_command_single_url(self):
        """Test command building with single URL input."""
        config = ToolConfig(name="nuclei", timeout=300, rate_limit=20)
        inputs = ["https://example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertEqual(cmd[0], str(self.bin_path / "nuclei"))
        self.assertIn("-json", cmd)
        self.assertIn("-silent", cmd)
        self.assertIn("-timeout", cmd)
        self.assertIn("300", cmd)
        self.assertIn("-rate-limit", cmd)
        self.assertIn("20", cmd)
        self.assertIn("-u", cmd)
        self.assertIn("https://example.com", cmd)

    def test_build_command_no_timeout(self):
        """Test command building without timeout."""
        config = ToolConfig(name="nuclei", timeout=0)
        inputs = ["https://example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertNotIn("-timeout", cmd)

    def test_build_command_no_rate_limit(self):
        """Test command building without rate limit."""
        config = ToolConfig(name="nuclei", rate_limit=None)
        inputs = ["https://example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertNotIn("-rate-limit", cmd)

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_file')
    def test_build_command_with_file_input(self, mock_is_file, mock_exists):
        """Test command building with file input."""
        mock_exists.return_value = True
        mock_is_file.return_value = True

        config = ToolConfig(name="nuclei", timeout=300)
        inputs = ["/tmp/targets.txt"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertIn("-list", cmd)
        self.assertIn("/tmp/targets.txt", cmd)
        self.assertNotIn("-u", cmd)

    def test_build_command_multiple_urls(self):
        """Test command building with multiple URLs (stdin mode)."""
        config = ToolConfig(name="nuclei", timeout=300)
        inputs = ["https://example.com", "https://test.com"]

        cmd = self.adapter.build_command(inputs, config)

        # Multiple URLs should not add -u or -list flag
        self.assertNotIn("-u", cmd)
        self.assertNotIn("-list", cmd)

    def test_build_command_with_custom_args(self):
        """Test command building with custom arguments."""
        config = ToolConfig(
            name="nuclei",
            timeout=300,
            args=["-severity", "high,critical", "-tags", "cve"]
        )
        inputs = ["https://example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertIn("-severity", cmd)
        self.assertIn("high,critical", cmd)
        self.assertIn("-tags", cmd)
        self.assertIn("cve", cmd)

    def test_parse_output_single_finding(self):
        """Test parsing single nuclei finding."""
        raw_output = json.dumps({
            "template-id": "CVE-2021-12345",
            "info": {
                "name": "Test Vulnerability",
                "description": "A test vulnerability description",
                "severity": "high",
                "tags": ["cve", "rce"],
                "reference": ["https://cve.mitre.org/CVE-2021-12345"]
            },
            "type": "http",
            "host": "https://example.com",
            "matched-at": "https://example.com/vulnerable",
            "timestamp": "2024-01-01T12:00:00Z"
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.type, "CVE-2021-12345")
        self.assertEqual(finding.severity, Severity.HIGH)
        self.assertEqual(finding.host, "https://example.com")
        self.assertEqual(finding.url, "https://example.com/vulnerable")
        self.assertEqual(finding.title, "Test Vulnerability")
        self.assertEqual(finding.tool, "nuclei")

    def test_parse_output_multiple_findings(self):
        """Test parsing multiple nuclei findings."""
        finding1 = json.dumps({
            "template-id": "CVE-2021-11111",
            "info": {"name": "Vuln 1", "severity": "critical"},
            "host": "https://example.com",
            "matched-at": "https://example.com/path1"
        })
        finding2 = json.dumps({
            "template-id": "CVE-2021-22222",
            "info": {"name": "Vuln 2", "severity": "medium"},
            "host": "https://test.com",
            "matched-at": "https://test.com/path2"
        })
        raw_output = f"{finding1}\n{finding2}"

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].type, "CVE-2021-11111")
        self.assertEqual(findings[1].type, "CVE-2021-22222")

    def test_parse_output_empty_string(self):
        """Test parsing empty output."""
        findings = self.adapter.parse_output("")

        self.assertEqual(len(findings), 0)

    def test_parse_output_malformed_json(self):
        """Test parsing malformed JSON is skipped."""
        raw_output = "not valid json\n{invalid}\n"

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 0)

    def test_map_severity_critical(self):
        """Test severity mapping for critical."""
        severity = self.adapter._map_severity("critical")
        self.assertEqual(severity, Severity.CRITICAL)

    def test_map_severity_high(self):
        """Test severity mapping for high."""
        severity = self.adapter._map_severity("high")
        self.assertEqual(severity, Severity.HIGH)

    def test_map_severity_medium(self):
        """Test severity mapping for medium."""
        severity = self.adapter._map_severity("medium")
        self.assertEqual(severity, Severity.MEDIUM)

    def test_map_severity_low(self):
        """Test severity mapping for low."""
        severity = self.adapter._map_severity("low")
        self.assertEqual(severity, Severity.LOW)

    def test_map_severity_info(self):
        """Test severity mapping for info."""
        severity = self.adapter._map_severity("info")
        self.assertEqual(severity, Severity.INFO)

    def test_map_severity_unknown(self):
        """Test severity mapping for unknown defaults to INFO."""
        severity = self.adapter._map_severity("unknown")
        self.assertEqual(severity, Severity.INFO)

    def test_map_severity_case_insensitive(self):
        """Test severity mapping is case-insensitive."""
        self.assertEqual(self.adapter._map_severity("CRITICAL"), Severity.CRITICAL)
        self.assertEqual(self.adapter._map_severity("High"), Severity.HIGH)
        self.assertEqual(self.adapter._map_severity("MeDiUm"), Severity.MEDIUM)

    def test_determine_confidence_with_extracted_results(self):
        """Test confidence is CONFIRMED with extracted results."""
        data = {
            "extracted-results": ["result1", "result2"],
            "matcher-name": "test"
        }

        confidence = self.adapter._determine_confidence(data)

        self.assertEqual(confidence, Confidence.CONFIRMED)

    def test_determine_confidence_with_verified_matcher(self):
        """Test confidence is CONFIRMED with verified matcher."""
        data = {"matcher-name": "verified-exploit"}

        confidence = self.adapter._determine_confidence(data)

        self.assertEqual(confidence, Confidence.CONFIRMED)

    def test_determine_confidence_with_rce_matcher(self):
        """Test confidence is CONFIRMED with RCE matcher."""
        data = {"matcher-name": "rce-detection"}

        confidence = self.adapter._determine_confidence(data)

        self.assertEqual(confidence, Confidence.CONFIRMED)

    def test_determine_confidence_with_cve_tag(self):
        """Test confidence is FIRM with CVE tag."""
        data = {
            "info": {"tags": ["cve", "2021"]},
            "matcher-name": "test"
        }

        confidence = self.adapter._determine_confidence(data)

        self.assertEqual(confidence, Confidence.FIRM)

    def test_determine_confidence_default_tentative(self):
        """Test confidence defaults to TENTATIVE."""
        data = {"matcher-name": "generic"}

        confidence = self.adapter._determine_confidence(data)

        self.assertEqual(confidence, Confidence.TENTATIVE)

    def test_extract_reproduction_steps(self):
        """Test extracting reproduction steps."""
        data = {
            "matched-at": "https://example.com/vuln",
            "matcher-name": "status-code-matcher",
            "extracted-results": ["secret1", "secret2", "secret3"]
        }

        steps = self.adapter._extract_reproduction_steps(data)

        self.assertGreater(len(steps), 0)
        self.assertIn("https://example.com/vuln", steps[0])
        self.assertTrue(any("status-code-matcher" in step for step in steps))
        self.assertTrue(any("secret1" in step for step in steps))

    def test_extract_reproduction_steps_minimal(self):
        """Test extracting reproduction steps with minimal data."""
        data = {"matched-at": "https://example.com/test"}

        steps = self.adapter._extract_reproduction_steps(data)

        self.assertEqual(len(steps), 1)
        self.assertIn("https://example.com/test", steps[0])

    def test_convert_to_finding_full_data(self):
        """Test converting complete nuclei output."""
        data = {
            "template-id": "CVE-2021-99999",
            "info": {
                "name": "Critical XSS",
                "description": "Cross-site scripting vulnerability",
                "severity": "critical",
                "tags": ["cve", "xss"],
                "reference": ["https://example.com/advisory"],
                "remediation": "Update to version 2.0"
            },
            "host": "https://example.com",
            "matched-at": "https://example.com/search?q=test",
            "matcher-name": "verified",
            "extracted-results": ["<script>alert(1)</script>"],
            "timestamp": "2024-01-01T12:00:00Z"
        }

        finding = self.adapter._convert_to_finding(data)

        self.assertIsNotNone(finding)
        self.assertEqual(finding.type, "CVE-2021-99999")
        self.assertEqual(finding.severity, Severity.CRITICAL)
        self.assertEqual(finding.confidence, Confidence.CONFIRMED)
        self.assertEqual(finding.title, "Critical XSS")
        self.assertEqual(finding.description, "Cross-site scripting vulnerability")
        self.assertEqual(finding.remediation, "Update to version 2.0")
        self.assertIn("https://example.com/advisory", finding.references)

    def test_convert_to_finding_minimal_data(self):
        """Test converting minimal nuclei output."""
        data = {
            "template-id": "test-template",
            "info": {"name": "Test Finding"},
            "host": "https://example.com"
        }

        finding = self.adapter._convert_to_finding(data)

        self.assertIsNotNone(finding)
        self.assertEqual(finding.type, "test-template")
        self.assertEqual(finding.host, "https://example.com")

    def test_convert_to_finding_uses_matched_at(self):
        """Test that matched-at URL is preferred over host."""
        data = {
            "template-id": "test",
            "info": {"name": "Test"},
            "host": "https://example.com",
            "matched-at": "https://example.com/specific/path"
        }

        finding = self.adapter._convert_to_finding(data)

        self.assertEqual(finding.url, "https://example.com/specific/path")

    def test_convert_to_finding_reference_string(self):
        """Test converting single reference string to list."""
        data = {
            "template-id": "test",
            "info": {
                "name": "Test",
                "reference": "https://single-reference.com"
            },
            "host": "https://example.com"
        }

        finding = self.adapter._convert_to_finding(data)

        self.assertIsInstance(finding.references, list)
        self.assertIn("https://single-reference.com", finding.references)

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_file')
    @patch('pathlib.Path.stat')
    async def test_check_available_success(self, mock_stat, mock_is_file, mock_exists):
        """Test check_available returns True when tool exists."""
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_stat_result = MagicMock()
        mock_stat_result.st_mode = 0o100755
        mock_stat.return_value = mock_stat_result

        available = await self.adapter.check_available()

        self.assertTrue(available)

    @patch('pathlib.Path.exists')
    async def test_check_available_not_found(self, mock_exists):
        """Test check_available returns False when tool not found."""
        mock_exists.return_value = False

        available = await self.adapter.check_available()

        self.assertFalse(available)


if __name__ == "__main__":
    unittest.main()
