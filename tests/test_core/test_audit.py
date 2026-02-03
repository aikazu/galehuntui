"""Unit tests for AuditLogger.

Tests cover:
- Initialization: creates directory, creates file, handles errors
- log_event: writes JSON, correct format, all 7 event types
- Timestamp: ISO 8601 UTC format with timezone
- Error handling: AuditLogError on failures
- close: cleanup and flushing
- Append mode: multiple logger instances
- JSON structure: run_id, event_type, details, timestamp
"""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from galehuntui.core.audit import AuditLogger
from galehuntui.core.constants import AuditEventType
from galehuntui.core.exceptions import AuditLogError


class TestAuditLoggerInitialization(unittest.TestCase):
    """Test AuditLogger initialization and setup."""
    
    def setUp(self):
        """Create temporary directory for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_dir = Path(self.temp_dir.name) / "run-test" / "audit"
        self.run_id = "test-run-001"
    
    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()
    
    def test_initialization_creates_directory(self):
        """Test that initialization creates audit directory if missing."""
        self.assertFalse(self.audit_dir.exists())
        
        logger = AuditLogger(run_id=self.run_id, audit_dir=self.audit_dir)
        
        self.assertTrue(self.audit_dir.exists())
        self.assertTrue(self.audit_dir.is_dir())
        logger.close()
    
    def test_initialization_creates_file(self):
        """Test that initialization creates audit.log file."""
        logger = AuditLogger(run_id=self.run_id, audit_dir=self.audit_dir)
        
        log_path = self.audit_dir / "audit.log"
        self.assertTrue(log_path.exists())
        self.assertTrue(log_path.is_file())
        logger.close()
    
    def test_initialization_sets_attributes(self):
        """Test that initialization sets run_id and paths correctly."""
        logger = AuditLogger(run_id=self.run_id, audit_dir=self.audit_dir)
        
        self.assertEqual(logger.run_id, self.run_id)
        self.assertEqual(logger.audit_dir, self.audit_dir)
        self.assertEqual(logger.log_path, self.audit_dir / "audit.log")
        logger.close()
    
    def test_initialization_directory_creation_error(self):
        """Test that AuditLogError is raised on directory creation failure."""
        # Use an invalid path that cannot be created (e.g., under a file)
        file_path = Path(self.temp_dir.name) / "blocking_file"
        file_path.write_text("block")
        
        invalid_dir = file_path / "cannot_create_dir"
        
        with self.assertRaises(AuditLogError) as ctx:
            AuditLogger(run_id=self.run_id, audit_dir=invalid_dir)
        
        self.assertIn("Failed to create audit directory", str(ctx.exception))


class TestAuditLoggerEventLogging(unittest.TestCase):
    """Test AuditLogger event logging functionality."""
    
    def setUp(self):
        """Create temporary directory and logger for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_dir = Path(self.temp_dir.name) / "run-test"
        self.run_id = "test-run-002"
        self.logger = AuditLogger(run_id=self.run_id, audit_dir=self.audit_dir)
        self.log_path = self.audit_dir / "audit.log"
    
    def tearDown(self):
        """Clean up logger and temporary directory."""
        self.logger.close()
        self.temp_dir.cleanup()
    
    def test_log_event_basic(self):
        """Test logging a basic event without details."""
        self.logger.log_event(AuditEventType.RUN_START)
        
        content = self.log_path.read_text().strip()
        self.assertTrue(len(content) > 0)
        
        event = json.loads(content)
        self.assertEqual(event["run_id"], self.run_id)
        self.assertEqual(event["event_type"], "run_start")
        self.assertEqual(event["details"], {})
    
    def test_log_event_with_details(self):
        """Test logging an event with custom details."""
        details = {"target": "example.com", "mode": "authorized"}
        
        self.logger.log_event(AuditEventType.RUN_START, details=details)
        
        content = self.log_path.read_text().strip()
        event = json.loads(content)
        
        self.assertEqual(event["details"], details)
        self.assertEqual(event["details"]["target"], "example.com")
        self.assertEqual(event["details"]["mode"], "authorized")
    
    def test_log_event_all_event_types(self):
        """Test logging all 7 AuditEventType values."""
        all_event_types = [
            AuditEventType.RUN_START,
            AuditEventType.RUN_FINISH,
            AuditEventType.TOOL_START,
            AuditEventType.TOOL_FINISH,
            AuditEventType.SCOPE_VIOLATION,
            AuditEventType.MODE_CHANGE,
            AuditEventType.FEATURE_TOGGLE,
        ]
        
        for event_type in all_event_types:
            self.logger.log_event(event_type)
        
        lines = self.log_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 7)
        
        for i, event_type in enumerate(all_event_types):
            event = json.loads(lines[i])
            self.assertEqual(event["event_type"], event_type.value)
    
    def test_log_event_json_format(self):
        """Test that events are written in valid JSON format."""
        self.logger.log_event(
            AuditEventType.TOOL_START,
            details={"tool": "subfinder", "stage": "subdomain_enumeration"}
        )
        
        content = self.log_path.read_text().strip()
        
        # Should parse as valid JSON
        event = json.loads(content)
        
        # Verify structure
        self.assertIn("timestamp", event)
        self.assertIn("run_id", event)
        self.assertIn("event_type", event)
        self.assertIn("details", event)
    
    def test_log_event_timestamp_iso8601_utc(self):
        """Test that timestamp is in ISO 8601 UTC format."""
        before = datetime.now(timezone.utc)
        self.logger.log_event(AuditEventType.RUN_START)
        after = datetime.now(timezone.utc)
        
        content = self.log_path.read_text().strip()
        event = json.loads(content)
        
        # Parse timestamp
        timestamp_str = event["timestamp"]
        timestamp = datetime.fromisoformat(timestamp_str)
        
        # Verify it's between before and after
        self.assertGreaterEqual(timestamp, before)
        self.assertLessEqual(timestamp, after)
        
        # Verify timezone is UTC
        self.assertEqual(timestamp.tzinfo, timezone.utc)
        
        # Verify ISO 8601 format (contains 'T' and timezone)
        self.assertIn("T", timestamp_str)
        self.assertTrue(timestamp_str.endswith("+00:00") or "Z" in timestamp_str)
    
    def test_log_event_multiple_events(self):
        """Test logging multiple events in sequence."""
        events = [
            (AuditEventType.RUN_START, {"target": "example.com"}),
            (AuditEventType.TOOL_START, {"tool": "subfinder"}),
            (AuditEventType.TOOL_FINISH, {"tool": "subfinder", "success": True}),
            (AuditEventType.RUN_FINISH, {"status": "completed"}),
        ]
        
        for event_type, details in events:
            self.logger.log_event(event_type, details=details)
        
        lines = self.log_path.read_text().strip().split("\n")
        self.assertEqual(len(lines), 4)
        
        # Verify each event
        for i, (event_type, details) in enumerate(events):
            event = json.loads(lines[i])
            self.assertEqual(event["event_type"], event_type.value)
            self.assertEqual(event["details"], details)


class TestAuditLoggerErrorHandling(unittest.TestCase):
    """Test AuditLogger error handling."""
    
    def setUp(self):
        """Create temporary directory for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_dir = Path(self.temp_dir.name) / "run-test"
        self.run_id = "test-run-003"
    
    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()
    
    def test_log_event_write_failure(self):
        """Test that AuditLogError is raised on write failures."""
        logger = AuditLogger(run_id=self.run_id, audit_dir=self.audit_dir)
        
        # Mock the logger to raise an exception on info()
        with patch.object(logger._logger, 'info', side_effect=Exception("Write failed")):
            with self.assertRaises(AuditLogError) as ctx:
                logger.log_event(AuditEventType.RUN_START)
            
            self.assertIn("Failed to write audit event", str(ctx.exception))
            self.assertIn("run_start", str(ctx.exception))
        
        logger.close()


class TestAuditLoggerCleanup(unittest.TestCase):
    """Test AuditLogger cleanup and resource management."""
    
    def setUp(self):
        """Create temporary directory for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_dir = Path(self.temp_dir.name) / "run-test"
        self.run_id = "test-run-004"
    
    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()
    
    def test_close_cleanup(self):
        """Test that close() flushes and closes handlers."""
        logger = AuditLogger(run_id=self.run_id, audit_dir=self.audit_dir)
        logger.log_event(AuditEventType.RUN_START)
        
        # Verify handler exists
        self.assertGreater(len(logger._logger.handlers), 0)
        
        logger.close()
        
        # Verify handlers are cleared
        self.assertEqual(len(logger._logger.handlers), 0)
    
    def test_append_mode(self):
        """Test that multiple logger instances append to the same file."""
        # First logger
        logger1 = AuditLogger(run_id=self.run_id, audit_dir=self.audit_dir)
        logger1.log_event(AuditEventType.RUN_START, {"iteration": 1})
        logger1.close()
        
        # Second logger (same run_id, same audit_dir)
        logger2 = AuditLogger(run_id=self.run_id, audit_dir=self.audit_dir)
        logger2.log_event(AuditEventType.RUN_FINISH, {"iteration": 2})
        logger2.close()
        
        # Verify both events are in the log
        log_path = self.audit_dir / "audit.log"
        lines = log_path.read_text().strip().split("\n")
        
        self.assertEqual(len(lines), 2)
        
        event1 = json.loads(lines[0])
        event2 = json.loads(lines[1])
        
        self.assertEqual(event1["event_type"], "run_start")
        self.assertEqual(event1["details"]["iteration"], 1)
        
        self.assertEqual(event2["event_type"], "run_finish")
        self.assertEqual(event2["details"]["iteration"], 2)


class TestAuditLoggerEdgeCases(unittest.TestCase):
    """Test AuditLogger edge cases and special scenarios."""
    
    def setUp(self):
        """Create temporary directory for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_dir = Path(self.temp_dir.name) / "run-test"
        self.run_id = "test-run-005"
    
    def tearDown(self):
        """Clean up temporary directory."""
        self.temp_dir.cleanup()
    
    def test_details_none_default(self):
        """Test that details=None defaults to empty dict."""
        logger = AuditLogger(run_id=self.run_id, audit_dir=self.audit_dir)
        logger.log_event(AuditEventType.RUN_START, details=None)
        
        log_path = self.audit_dir / "audit.log"
        content = log_path.read_text().strip()
        event = json.loads(content)
        
        self.assertEqual(event["details"], {})
        logger.close()
    
    def test_complex_details_serialization(self):
        """Test that complex details are properly JSON serialized."""
        logger = AuditLogger(run_id=self.run_id, audit_dir=self.audit_dir)
        
        details = {
            "target": "example.com",
            "findings": 42,
            "duration": 123.456,
            "nested": {"key": "value", "list": [1, 2, 3]},
            "boolean": True,
        }
        
        logger.log_event(AuditEventType.RUN_FINISH, details=details)
        
        log_path = self.audit_dir / "audit.log"
        content = log_path.read_text().strip()
        event = json.loads(content)
        
        self.assertEqual(event["details"], details)
        self.assertEqual(event["details"]["findings"], 42)
        self.assertEqual(event["details"]["duration"], 123.456)
        self.assertEqual(event["details"]["nested"]["list"], [1, 2, 3])
        self.assertTrue(event["details"]["boolean"])
        logger.close()
    
    def test_run_id_isolation(self):
        """Test that different run_ids create separate logger instances."""
        logger1 = AuditLogger(run_id="run-001", audit_dir=self.audit_dir)
        logger2 = AuditLogger(run_id="run-002", audit_dir=self.audit_dir)
        
        self.assertEqual(logger1.run_id, "run-001")
        self.assertEqual(logger2.run_id, "run-002")
        
        # Different logger instances
        self.assertNotEqual(logger1._logger.name, logger2._logger.name)
        self.assertIn("run-001", logger1._logger.name)
        self.assertIn("run-002", logger2._logger.name)
        
        logger1.close()
        logger2.close()


if __name__ == "__main__":
    unittest.main()
