"""Unit tests for SubfinderAdapter.

Tests command building, output parsing, and core logic without requiring
the actual subfinder binary to be installed.
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
from galehuntui.tools.adapters.subfinder import SubfinderAdapter


class TestSubfinderAdapter(unittest.IsolatedAsyncioTestCase):
    """Test cases for SubfinderAdapter."""

    def setUp(self):
        """Set up test fixtures."""
        self.bin_path = Path("/mock/tools/bin")
        self.adapter = SubfinderAdapter(self.bin_path)

    def test_adapter_attributes(self):
        """Test adapter has correct attributes."""
        self.assertEqual(self.adapter.name, "subfinder")
        self.assertTrue(self.adapter.required)
        self.assertIsNone(self.adapter.mode_required)

    def test_build_command_single_domain(self):
        """Test command building with single domain input."""
        config = ToolConfig(name="subfinder", timeout=60)
        inputs = ["example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertEqual(cmd[0], str(self.bin_path / "subfinder"))
        self.assertIn("-json", cmd)
        self.assertIn("-silent", cmd)
        self.assertIn("-timeout", cmd)
        self.assertIn("60", cmd)
        self.assertIn("-d", cmd)
        self.assertIn("example.com", cmd)

    def test_build_command_no_timeout(self):
        """Test command building without timeout."""
        config = ToolConfig(name="subfinder", timeout=0)
        inputs = ["example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertNotIn("-timeout", cmd)

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_file')
    def test_build_command_with_file_input(self, mock_is_file, mock_exists):
        """Test command building with file input."""
        mock_exists.return_value = True
        mock_is_file.return_value = True

        config = ToolConfig(name="subfinder", timeout=60)
        inputs = ["/tmp/domains.txt"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertIn("-list", cmd)
        self.assertIn("/tmp/domains.txt", cmd)
        self.assertNotIn("-d", cmd)

    def test_build_command_multiple_domains(self):
        """Test command building with multiple domains (stdin mode)."""
        config = ToolConfig(name="subfinder", timeout=60)
        inputs = ["example.com", "test.com"]

        cmd = self.adapter.build_command(inputs, config)

        # Multiple domains should not add -d or -list flag
        # They will be passed via stdin
        self.assertNotIn("-d", cmd)
        self.assertNotIn("-list", cmd)

    def test_build_command_with_custom_args(self):
        """Test command building with custom arguments."""
        config = ToolConfig(
            name="subfinder",
            timeout=60,
            args=["-all", "-recursive"]
        )
        inputs = ["example.com"]

        cmd = self.adapter.build_command(inputs, config)

        self.assertIn("-all", cmd)
        self.assertIn("-recursive", cmd)

    def test_parse_output_single_subdomain(self):
        """Test parsing single subfinder JSON output."""
        raw_output = json.dumps({
            "host": "www.example.com",
            "source": "virustotal",
            "timestamp": "2024-01-01T12:00:00Z"
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual(finding.host, "www.example.com")
        self.assertEqual(finding.url, "www.example.com")
        self.assertEqual(finding.type, "subdomain")
        self.assertEqual(finding.severity, Severity.INFO)
        self.assertEqual(finding.confidence, Confidence.CONFIRMED)
        self.assertEqual(finding.tool, "subfinder")
        self.assertIn("www.example.com", finding.title)
        self.assertIn("virustotal", finding.description)

    def test_parse_output_multiple_subdomains(self):
        """Test parsing multiple subfinder JSON outputs."""
        subdomain1 = json.dumps({
            "host": "www.example.com",
            "source": "virustotal"
        })
        subdomain2 = json.dumps({
            "host": "api.example.com",
            "source": "certspotter"
        })
        subdomain3 = json.dumps({
            "host": "mail.example.com",
            "source": "crtsh"
        })
        raw_output = f"{subdomain1}\n{subdomain2}\n{subdomain3}"

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 3)
        self.assertEqual(findings[0].host, "www.example.com")
        self.assertEqual(findings[1].host, "api.example.com")
        self.assertEqual(findings[2].host, "mail.example.com")

    def test_parse_output_empty_string(self):
        """Test parsing empty output."""
        findings = self.adapter.parse_output("")

        self.assertEqual(len(findings), 0)

    def test_parse_output_malformed_json(self):
        """Test parsing malformed JSON is skipped."""
        raw_output = "not valid json\n{invalid json}\n"

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 0)

    def test_parse_output_missing_host(self):
        """Test parsing JSON without host is skipped."""
        raw_output = json.dumps({
            "source": "virustotal",
            "timestamp": "2024-01-01T12:00:00Z"
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 0)

    def test_parse_output_with_timestamp(self):
        """Test parsing output with timestamp."""
        raw_output = json.dumps({
            "host": "test.example.com",
            "source": "dnsdumpster",
            "timestamp": "2024-01-01T12:00:00Z"
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 1)
        self.assertIsInstance(findings[0].timestamp, datetime)

    def test_parse_output_missing_timestamp(self):
        """Test parsing without timestamp uses current time."""
        raw_output = json.dumps({
            "host": "test.example.com",
            "source": "certspotter"
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 1)
        self.assertIsInstance(findings[0].timestamp, datetime)

    def test_parse_output_invalid_timestamp(self):
        """Test parsing with invalid timestamp uses current time."""
        raw_output = json.dumps({
            "host": "test.example.com",
            "source": "virustotal",
            "timestamp": "invalid-timestamp"
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 1)
        self.assertIsInstance(findings[0].timestamp, datetime)

    def test_parse_output_unknown_source(self):
        """Test parsing without source defaults to unknown."""
        raw_output = json.dumps({
            "host": "test.example.com"
        })

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 1)
        self.assertIn("unknown", findings[0].description)

    def test_parse_output_different_sources(self):
        """Test parsing subdomains from different sources."""
        sources = ["virustotal", "certspotter", "crtsh", "dnsdumpster", "shodan"]
        outputs = []
        for i, source in enumerate(sources):
            outputs.append(json.dumps({
                "host": f"sub{i}.example.com",
                "source": source
            }))
        raw_output = "\n".join(outputs)

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 5)
        for i, finding in enumerate(findings):
            self.assertIn(sources[i], finding.description)

    def test_parse_output_exception_handling(self):
        """Test parsing handles exceptions gracefully."""
        # Mix of valid and invalid entries
        valid = json.dumps({"host": "valid.example.com", "source": "test"})
        invalid = "not json"
        no_host = json.dumps({"source": "test"})
        raw_output = f"{valid}\n{invalid}\n{no_host}"

        findings = self.adapter.parse_output(raw_output)

        # Only the valid entry should be parsed
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].host, "valid.example.com")

    def test_finding_attributes(self):
        """Test all finding attributes are set correctly."""
        raw_output = json.dumps({
            "host": "subdomain.example.com",
            "source": "virustotal",
            "timestamp": "2024-01-01T12:00:00Z"
        })

        findings = self.adapter.parse_output(raw_output)
        finding = findings[0]

        # Check all required attributes
        self.assertIsNotNone(finding.id)
        self.assertEqual(finding.run_id, "")  # Set by orchestrator
        self.assertEqual(finding.type, "subdomain")
        self.assertEqual(finding.severity, Severity.INFO)
        self.assertEqual(finding.confidence, Confidence.CONFIRMED)
        self.assertEqual(finding.host, "subdomain.example.com")
        self.assertEqual(finding.url, "subdomain.example.com")
        self.assertIsNone(finding.parameter)
        self.assertEqual(finding.evidence_paths, [])
        self.assertEqual(finding.tool, "subfinder")
        self.assertIsInstance(finding.timestamp, datetime)

        # Check extended attributes
        self.assertIn("subdomain.example.com", finding.title)
        self.assertIn("virustotal", finding.description)
        self.assertEqual(len(finding.reproduction_steps), 1)
        self.assertIsNone(finding.remediation)
        self.assertEqual(finding.references, [])

    def test_reproduction_steps_format(self):
        """Test reproduction steps are formatted correctly."""
        raw_output = json.dumps({
            "host": "test.example.com",
            "source": "certspotter"
        })

        findings = self.adapter.parse_output(raw_output)
        finding = findings[0]

        self.assertEqual(len(finding.reproduction_steps), 1)
        self.assertIn("certspotter", finding.reproduction_steps[0])

    def test_parse_output_whitespace_handling(self):
        """Test parsing handles extra whitespace correctly."""
        subdomain1 = json.dumps({"host": "www.example.com", "source": "test"})
        subdomain2 = json.dumps({"host": "api.example.com", "source": "test"})
        # Add extra newlines and whitespace
        raw_output = f"\n\n{subdomain1}\n\n\n{subdomain2}\n\n"

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 2)

    def test_parse_output_large_dataset(self):
        """Test parsing large number of subdomains."""
        outputs = []
        for i in range(100):
            outputs.append(json.dumps({
                "host": f"sub{i}.example.com",
                "source": "virustotal"
            }))
        raw_output = "\n".join(outputs)

        findings = self.adapter.parse_output(raw_output)

        self.assertEqual(len(findings), 100)
        # Verify first and last
        self.assertEqual(findings[0].host, "sub0.example.com")
        self.assertEqual(findings[99].host, "sub99.example.com")

    @patch('pathlib.Path.exists')
    def test_get_tool_path(self, mock_exists):
        """Test getting tool path."""
        tool_path = self.adapter._get_tool_path()

        self.assertEqual(tool_path, self.bin_path / "subfinder")

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

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_file')
    async def test_check_available_not_file(self, mock_is_file, mock_exists):
        """Test check_available returns False when path is not a file."""
        mock_exists.return_value = True
        mock_is_file.return_value = False

        available = await self.adapter.check_available()

        self.assertFalse(available)

    @patch('pathlib.Path.exists')
    @patch('pathlib.Path.is_file')
    @patch('pathlib.Path.stat')
    async def test_check_available_not_executable(self, mock_stat, mock_is_file, mock_exists):
        """Test check_available returns False when file is not executable."""
        mock_exists.return_value = True
        mock_is_file.return_value = True
        # Mock non-executable file (0o644)
        mock_stat_result = MagicMock()
        mock_stat_result.st_mode = 0o100644
        mock_stat.return_value = mock_stat_result

        available = await self.adapter.check_available()

        self.assertFalse(available)


if __name__ == "__main__":
    unittest.main()
