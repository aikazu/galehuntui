"""Unit tests for HttpxAdapter.

Tests command building, output parsing, and core logic without requiring
the actual httpx binary to be installed.
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
from galehuntui.tools.adapters.httpx import HttpxAdapter


class TestHttpxAdapter(unittest.IsolatedAsyncioTestCase):
    """Test cases for HttpxAdapter."""

    def setUp(self):
        """Set up test fixtures."""
        self.bin_path = Path("/mock/tools/bin")
        self.adapter = HttpxAdapter(self.bin_path)

    def test_adapter_attributes(self):
        """Test adapter has correct attributes."""
        self.assertEqual(self.adapter.name, "httpx")
        self.assertTrue(self.adapter.required)
        self.assertIsNone(self.adapter.mode_required)

    def test_build_command_single_url(self):
        """Test command building with single URL input."""
        config = ToolConfig(name="httpx", timeout=30, rate_limit=10)
        inputs = ["https://example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertEqual(cmd[0], str(self.bin_path / "httpx"))
        self.assertIn("-json", cmd)
        self.assertIn("-silent", cmd)
        self.assertIn("-timeout", cmd)
        self.assertIn("30", cmd)
        self.assertIn("-rate-limit", cmd)
        self.assertIn("10", cmd)
        self.assertIn("-u", cmd)
        self.assertIn("https://example.com", cmd)

    def test_build_command_no_timeout(self):
        """Test command building without timeout."""
        config = ToolConfig(name="httpx", timeout=0)
        inputs = ["https://example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertNotIn("-timeout", cmd)

    def test_build_command_no_rate_limit(self):
        """Test command building without rate limit."""
        config = ToolConfig(name="httpx", rate_limit=None)
        inputs = ["https://example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertNotIn("-rate-limit", cmd)

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_file')
    def test_build_command_with_file_input(self, mock_is_file, mock_exists):
        """Test command building with file input."""
        mock_exists.return_value = True
        mock_is_file.return_value = True

        config = ToolConfig(name="httpx", timeout=30)
        inputs = ["/tmp/urls.txt"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertIn("-list", cmd)
        self.assertIn("/tmp/urls.txt", cmd)
        self.assertNotIn("-u", cmd)

    def test_build_command_multiple_urls(self):
        """Test command building with multiple URLs (stdin mode)."""
        config = ToolConfig(name="httpx", timeout=30)
        inputs = ["https://example.com", "https://test.com"]

        cmd = self.adapter.build_command(inputs, config)

        # Multiple URLs should not add -u or -list flag
        # They will be passed via stdin
        self.assertNotIn("-u", cmd)
        self.assertNotIn("-list", cmd)

    def test_build_command_with_custom_args(self):
        """Test command building with custom arguments."""
        config = ToolConfig(
            name="httpx",
            timeout=30,
            args=["-follow-redirects", "-status-code"]
        )
        inputs = ["https://example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertIn("-follow-redirects", cmd)
        self.assertIn("-status-code", cmd)

    def test_parse_output_single_result(self):
        """Test parsing single httpx JSON output."""
        raw_output = json.dumps({
            "url": "https://example.com",
            "host": "example.com",
            "status_code": 200,
            "title": "Example Domain",
            "webserver": "nginx",
            "technologies": ["Bootstrap", "jQuery"],
            "timestamp": "2024-01-01T12:00:00Z"
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.url, "https://example.com")
        self.assertEqual(finding.host, "example.com")
        self.assertEqual(finding.type, "http_probe")
        self.assertEqual(finding.severity, Severity.INFO)
        self.assertEqual(finding.confidence, Confidence.CONFIRMED)
        self.assertEqual(finding.tool, "httpx")
        self.assertIn("Example Domain", finding.title)
        self.assertIn("200", finding.description)
        self.assertIn("nginx", finding.description)

    def test_parse_output_multiple_results(self):
        """Test parsing multiple httpx JSON outputs."""
        result1 = json.dumps({
            "url": "https://example.com",
            "host": "example.com",
            "status_code": 200,
            "title": "Example Domain"
        })
        result2 = json.dumps({
            "url": "https://test.com",
            "host": "test.com",
            "status_code": 404,
            "title": "Not Found"
        })
        raw_output = f"{result1}\n{result2}"

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].url, "https://example.com")
        self.assertEqual(findings[1].url, "https://test.com")

    def test_parse_output_empty_string(self):
        """Test parsing empty output."""
        findings = self.adapter.parse_output("")

        self.assertEqual(len(findings), 0)

    def test_parse_output_malformed_json(self):
        """Test parsing malformed JSON is skipped."""
        raw_output = "not valid json\n{invalid json}\n"

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 0)

    def test_parse_output_missing_url(self):
        """Test parsing JSON without URL is skipped."""
        raw_output = json.dumps({
            "host": "example.com",
            "status_code": 200
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 0)

    def test_parse_output_with_technologies(self):
        """Test parsing output with technologies."""
        raw_output = json.dumps({
            "url": "https://example.com",
            "host": "example.com",
            "technologies": ["React", "Webpack", "Node.js"]
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 1)
        self.assertIn("React", findings[0].description)
        self.assertIn("Webpack", findings[0].description)

    def test_parse_output_timestamp_parsing(self):
        """Test parsing with various timestamp formats."""
        raw_output = json.dumps({
            "url": "https://example.com",
            "host": "example.com",
            "timestamp": "2024-01-01T12:00:00Z"
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 1)
        self.assertIsInstance(findings[0].timestamp, datetime)

    def test_parse_output_missing_timestamp(self):
        """Test parsing without timestamp uses current time."""
        raw_output = json.dumps({
            "url": "https://example.com",
            "host": "example.com"
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 1)
        self.assertIsInstance(findings[0].timestamp, datetime)

    def test_convert_to_finding_minimal_data(self):
        """Test converting minimal httpx output to finding."""
        data = {
            "url": "https://example.com",
            "host": "example.com"
        }

        finding = self.adapter._convert_to_finding(data)

        self.assertIsNotNone(finding)
        self.assertEqual(finding.url, "https://example.com")
        self.assertEqual(finding.host, "example.com")
        self.assertEqual(finding.type, "http_probe")

    def test_convert_to_finding_no_url(self):
        """Test converting data without URL returns None."""
        data = {"host": "example.com"}

        finding = self.adapter._convert_to_finding(data)

        self.assertIsNone(finding)

    def test_convert_to_finding_full_data(self):
        """Test converting complete httpx output."""
        data = {
            "url": "https://example.com/path",
            "host": "example.com",
            "status_code": 200,
            "title": "Test Page",
            "webserver": "Apache/2.4",
            "technologies": ["PHP", "MySQL"],
            "timestamp": "2024-01-01T12:00:00Z"
        }

        finding = self.adapter._convert_to_finding(data)

        self.assertIsNotNone(finding)
        self.assertEqual(finding.url, "https://example.com/path")
        self.assertEqual(finding.title, "Live HTTP Endpoint: Test Page")
        self.assertIn("200", finding.description)
        self.assertIn("Apache/2.4", finding.description)
        self.assertIn("PHP", finding.description)
        self.assertEqual(len(finding.reproduction_steps), 1)

    @patch('pathlib.Path.exists')
    def test_get_tool_path(self, mock_exists):
        """Test getting tool path."""
        tool_path = self.adapter._get_tool_path()

        self.assertEqual(tool_path, self.bin_path / "httpx")

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_file')
    @patch('pathlib.Path.stat')
    async def test_check_available_success(self, mock_stat, mock_is_file, mock_exists):
        """Test check_available returns True when tool exists."""
        mock_exists.return_value = True
        mock_is_file.return_value = True
        # Mock executable file (0o755)
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
