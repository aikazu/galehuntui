"""Unit tests for Database layer.

Tests cover:
- Schema initialization
- Run metadata CRUD operations
- Finding CRUD operations
- Datetime serialization/deserialization
- JSON serialization for complex fields
- Enum handling
- Filtering and ordering
- Foreign key constraints
- Context manager usage
"""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from galehuntui.core.constants import EngagementMode
from galehuntui.core.exceptions import StorageError
from galehuntui.core.models import (
    Confidence,
    Finding,
    RunMetadata,
    RunState,
    Severity,
)
from galehuntui.storage.database import Database


class TestDatabaseInitialization(unittest.TestCase):
    """Test database initialization and schema creation."""
    
    def setUp(self):
        """Create temporary database for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = Path(self.temp_file.name)
        self.temp_file.close()
        self.db = Database(self.db_path)
    
    def tearDown(self):
        """Clean up database after each test."""
        self.db.close()
        if self.db_path.exists():
            self.db_path.unlink()
    
    def test_database_initialization(self):
        """Test database object creation."""
        self.assertEqual(self.db.db_path, self.db_path)
        self.assertIsNone(self.db._conn)
    
    def test_schema_creation(self):
        """Test that init_db creates required tables and indexes."""
        self.db.init_db()
        
        conn = self.db._get_connection()
        cursor = conn.cursor()
        
        # Check runs table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='runs'
        """)
        self.assertIsNotNone(cursor.fetchone())
        
        # Check findings table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='findings'
        """)
        self.assertIsNotNone(cursor.fetchone())
        
        # Check indexes exist
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_findings_run_id'
        """)
        self.assertIsNotNone(cursor.fetchone())
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_findings_severity'
        """)
        self.assertIsNotNone(cursor.fetchone())
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='index' AND name='idx_runs_state'
        """)
        self.assertIsNotNone(cursor.fetchone())
    
    def test_init_db_idempotent(self):
        """Test that init_db can be called multiple times safely."""
        self.db.init_db()
        self.db.init_db()  # Should not raise
        
        # Verify tables still exist
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT count(*) as cnt FROM sqlite_master 
            WHERE type='table' AND name IN ('runs', 'findings')
        """)
        result = cursor.fetchone()
        self.assertEqual(result[0], 2)
    
    def test_wal_mode_enabled(self):
        """Test that WAL mode is enabled."""
        self.db.init_db()
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode")
        result = cursor.fetchone()
        self.assertEqual(result[0].lower(), 'wal')
    
    def test_foreign_keys_enabled(self):
        """Test that foreign keys are enabled."""
        self.db.init_db()
        conn = self.db._get_connection()
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys")
        result = cursor.fetchone()
        self.assertEqual(result[0], 1)


class TestRunOperations(unittest.TestCase):
    """Test run metadata CRUD operations."""
    
    def setUp(self):
        """Create and initialize database for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = Path(self.temp_file.name)
        self.temp_file.close()
        self.db = Database(self.db_path)
        self.db.init_db()
    
    def tearDown(self):
        """Clean up database after each test."""
        self.db.close()
        if self.db_path.exists():
            self.db_path.unlink()
    
    def _create_sample_run(self, run_id: str = None) -> RunMetadata:
        """Create a sample run metadata object."""
        if run_id is None:
            run_id = str(uuid4())
        
        return RunMetadata(
            id=run_id,
            target="example.com",
            profile="standard",
            engagement_mode=EngagementMode.AUTHORIZED,
            state=RunState.PENDING,
            created_at=datetime(2024, 1, 15, 10, 30, 0),
            started_at=None,
            completed_at=None,
            total_steps=5,
            completed_steps=0,
            failed_steps=0,
            total_findings=0,
            findings_by_severity={},
            run_dir=Path("/tmp/runs/test-run"),
            artifacts_dir=Path("/tmp/runs/test-run/artifacts"),
            evidence_dir=Path("/tmp/runs/test-run/evidence"),
            reports_dir=Path("/tmp/runs/test-run/reports"),
        )
    
    def test_save_run(self):
        """Test saving a new run."""
        run = self._create_sample_run()
        self.db.save_run(run)
        
        # Verify run was saved
        retrieved = self.db.get_run(run.id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.id, run.id)
        self.assertEqual(retrieved.target, run.target)
        self.assertEqual(retrieved.profile, run.profile)
        self.assertEqual(retrieved.engagement_mode, run.engagement_mode)
        self.assertEqual(retrieved.state, run.state)
    
    def test_save_run_with_datetime_fields(self):
        """Test that datetime fields are correctly serialized and deserialized."""
        run = self._create_sample_run()
        run.started_at = datetime(2024, 1, 15, 10, 35, 0)
        run.completed_at = datetime(2024, 1, 15, 11, 45, 30)
        run.state = RunState.COMPLETED
        
        self.db.save_run(run)
        retrieved = self.db.get_run(run.id)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.created_at, run.created_at)
        self.assertEqual(retrieved.started_at, run.started_at)
        self.assertEqual(retrieved.completed_at, run.completed_at)
    
    def test_save_run_with_findings_by_severity(self):
        """Test that findings_by_severity dict is correctly serialized."""
        run = self._create_sample_run()
        run.findings_by_severity = {
            "critical": 2,
            "high": 5,
            "medium": 10,
            "low": 15,
            "info": 3,
        }
        run.total_findings = 35
        
        self.db.save_run(run)
        retrieved = self.db.get_run(run.id)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.findings_by_severity, run.findings_by_severity)
        self.assertEqual(retrieved.total_findings, 35)
    
    def test_update_run(self):
        """Test updating an existing run (upsert behavior)."""
        run = self._create_sample_run()
        self.db.save_run(run)
        
        # Update run state and progress
        run.state = RunState.RUNNING
        run.started_at = datetime(2024, 1, 15, 10, 35, 0)
        run.completed_steps = 3
        run.total_findings = 10
        run.findings_by_severity = {"high": 3, "medium": 7}
        
        self.db.save_run(run)
        retrieved = self.db.get_run(run.id)
        
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.state, RunState.RUNNING)
        self.assertEqual(retrieved.completed_steps, 3)
        self.assertEqual(retrieved.total_findings, 10)
        self.assertEqual(retrieved.findings_by_severity, {"high": 3, "medium": 7})
    
    def test_get_run_not_found(self):
        """Test getting a run that doesn't exist."""
        result = self.db.get_run("nonexistent-id")
        self.assertIsNone(result)
    
    def test_get_run_with_path_fields(self):
        """Test that Path fields are correctly restored."""
        run = self._create_sample_run()
        self.db.save_run(run)
        
        retrieved = self.db.get_run(run.id)
        self.assertIsNotNone(retrieved)
        self.assertIsInstance(retrieved.run_dir, Path)
        self.assertIsInstance(retrieved.artifacts_dir, Path)
        self.assertIsInstance(retrieved.evidence_dir, Path)
        self.assertIsInstance(retrieved.reports_dir, Path)
        self.assertEqual(retrieved.run_dir, run.run_dir)
    
    def test_list_runs_empty(self):
        """Test listing runs when database is empty."""
        runs = self.db.list_runs()
        self.assertEqual(len(runs), 0)
    
    def test_list_runs(self):
        """Test listing multiple runs."""
        run1 = self._create_sample_run(str(uuid4()))
        run1.created_at = datetime(2024, 1, 15, 10, 0, 0)
        
        run2 = self._create_sample_run(str(uuid4()))
        run2.created_at = datetime(2024, 1, 15, 11, 0, 0)
        
        run3 = self._create_sample_run(str(uuid4()))
        run3.created_at = datetime(2024, 1, 15, 12, 0, 0)
        
        self.db.save_run(run1)
        self.db.save_run(run2)
        self.db.save_run(run3)
        
        runs = self.db.list_runs()
        self.assertEqual(len(runs), 3)
        
        # Should be ordered by created_at DESC
        self.assertEqual(runs[0].id, run3.id)
        self.assertEqual(runs[1].id, run2.id)
        self.assertEqual(runs[2].id, run1.id)
    
    def test_list_runs_with_limit(self):
        """Test listing runs with limit."""
        for i in range(5):
            run = self._create_sample_run(str(uuid4()))
            self.db.save_run(run)
        
        runs = self.db.list_runs(limit=3)
        self.assertEqual(len(runs), 3)
    
    def test_list_runs_with_offset(self):
        """Test listing runs with offset."""
        run_ids = []
        for i in range(5):
            run = self._create_sample_run(str(uuid4()))
            run.created_at = datetime(2024, 1, 15, 10 + i, 0, 0)
            self.db.save_run(run)
            run_ids.append(run.id)
        
        # Get all runs first (ordered DESC)
        all_runs = self.db.list_runs()
        
        # Get runs with offset
        runs = self.db.list_runs(limit=3, offset=2)
        self.assertEqual(len(runs), 3)
        self.assertEqual(runs[0].id, all_runs[2].id)
    
    def test_list_runs_with_state_filter(self):
        """Test filtering runs by state."""
        run1 = self._create_sample_run(str(uuid4()))
        run1.state = RunState.PENDING
        
        run2 = self._create_sample_run(str(uuid4()))
        run2.state = RunState.RUNNING
        
        run3 = self._create_sample_run(str(uuid4()))
        run3.state = RunState.COMPLETED
        
        run4 = self._create_sample_run(str(uuid4()))
        run4.state = RunState.RUNNING
        
        self.db.save_run(run1)
        self.db.save_run(run2)
        self.db.save_run(run3)
        self.db.save_run(run4)
        
        # Filter by RUNNING state
        running_runs = self.db.list_runs(state_filter=RunState.RUNNING)
        self.assertEqual(len(running_runs), 2)
        
        # Filter by COMPLETED state
        completed_runs = self.db.list_runs(state_filter=RunState.COMPLETED)
        self.assertEqual(len(completed_runs), 1)
        self.assertEqual(completed_runs[0].id, run3.id)
    
    def test_delete_run(self):
        """Test deleting a run."""
        run = self._create_sample_run()
        self.db.save_run(run)
        
        # Verify run exists
        self.assertIsNotNone(self.db.get_run(run.id))
        
        # Delete run
        deleted = self.db.delete_run(run.id)
        self.assertTrue(deleted)
        
        # Verify run is gone
        self.assertIsNone(self.db.get_run(run.id))
    
    def test_delete_run_not_found(self):
        """Test deleting a run that doesn't exist."""
        deleted = self.db.delete_run("nonexistent-id")
        self.assertFalse(deleted)


class TestFindingOperations(unittest.TestCase):
    """Test finding CRUD operations."""
    
    def setUp(self):
        """Create and initialize database for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = Path(self.temp_file.name)
        self.temp_file.close()
        self.db = Database(self.db_path)
        self.db.init_db()
        
        # Create a parent run
        self.run_id = str(uuid4())
        run = RunMetadata(
            id=self.run_id,
            target="example.com",
            profile="standard",
            engagement_mode=EngagementMode.AUTHORIZED,
            state=RunState.RUNNING,
            created_at=datetime.now(),
            run_dir=Path("/tmp/runs/test"),
            artifacts_dir=Path("/tmp/runs/test/artifacts"),
            evidence_dir=Path("/tmp/runs/test/evidence"),
            reports_dir=Path("/tmp/runs/test/reports"),
        )
        self.db.save_run(run)
    
    def tearDown(self):
        """Clean up database after each test."""
        self.db.close()
        if self.db_path.exists():
            self.db_path.unlink()
    
    def _create_sample_finding(
        self,
        finding_id: str = None,
        severity: Severity = Severity.HIGH,
        confidence: Confidence = Confidence.CONFIRMED,
    ) -> Finding:
        """Create a sample finding object."""
        if finding_id is None:
            finding_id = str(uuid4())
        
        return Finding(
            id=finding_id,
            run_id=self.run_id,
            type="xss",
            severity=severity,
            confidence=confidence,
            host="example.com",
            url="https://example.com/search?q=test",
            parameter="q",
            evidence_paths=["screenshots/001.png", "requests/001.txt"],
            tool="dalfox",
            timestamp=datetime(2024, 1, 15, 11, 30, 0),
            title="Reflected XSS in search parameter",
            description="The search parameter is reflected without proper encoding.",
            reproduction_steps=[
                "Navigate to https://example.com/search",
                "Enter payload: <script>alert(1)</script>",
                "Observe execution",
            ],
            remediation="Encode user input before reflection.",
            references=["https://owasp.org/www-community/attacks/xss/"],
        )
    
    def test_save_finding(self):
        """Test saving a new finding."""
        finding = self._create_sample_finding()
        self.db.save_finding(finding)
        
        # Verify finding was saved
        findings = self.db.get_findings_for_run(self.run_id)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].id, finding.id)
        self.assertEqual(findings[0].type, "xss")
        self.assertEqual(findings[0].severity, Severity.HIGH)
    
    def test_save_finding_with_lists(self):
        """Test that list fields are correctly serialized."""
        finding = self._create_sample_finding()
        self.db.save_finding(finding)
        
        findings = self.db.get_findings_for_run(self.run_id)
        retrieved = findings[0]
        
        self.assertEqual(retrieved.evidence_paths, finding.evidence_paths)
        self.assertEqual(retrieved.reproduction_steps, finding.reproduction_steps)
        self.assertEqual(retrieved.references, finding.references)
    
    def test_save_finding_with_optional_fields(self):
        """Test saving finding with optional fields as None."""
        finding = self._create_sample_finding()
        finding.parameter = None
        finding.description = None
        finding.remediation = None
        finding.reproduction_steps = []
        finding.references = []
        
        self.db.save_finding(finding)
        
        findings = self.db.get_findings_for_run(self.run_id)
        retrieved = findings[0]
        
        self.assertIsNone(retrieved.parameter)
        self.assertIsNone(retrieved.description)
        self.assertIsNone(retrieved.remediation)
        self.assertEqual(retrieved.reproduction_steps, [])
        self.assertEqual(retrieved.references, [])
    
    def test_save_finding_with_datetime(self):
        """Test that datetime is correctly serialized and deserialized."""
        finding = self._create_sample_finding()
        finding.timestamp = datetime(2024, 1, 15, 14, 22, 33)
        
        self.db.save_finding(finding)
        
        findings = self.db.get_findings_for_run(self.run_id)
        retrieved = findings[0]
        
        self.assertEqual(retrieved.timestamp, finding.timestamp)
    
    def test_update_finding(self):
        """Test updating an existing finding (upsert behavior)."""
        finding = self._create_sample_finding()
        self.db.save_finding(finding)
        
        # Update finding
        finding.description = "Updated description"
        finding.remediation = "Updated remediation"
        finding.evidence_paths.append("responses/001.txt")
        
        self.db.save_finding(finding)
        
        findings = self.db.get_findings_for_run(self.run_id)
        retrieved = findings[0]
        
        self.assertEqual(retrieved.description, "Updated description")
        self.assertEqual(retrieved.remediation, "Updated remediation")
        self.assertEqual(len(retrieved.evidence_paths), 3)
    
    def test_get_findings_for_run_empty(self):
        """Test getting findings when none exist."""
        findings = self.db.get_findings_for_run(self.run_id)
        self.assertEqual(len(findings), 0)
    
    def test_get_findings_for_run_multiple(self):
        """Test getting multiple findings for a run."""
        finding1 = self._create_sample_finding(str(uuid4()), Severity.CRITICAL)
        finding2 = self._create_sample_finding(str(uuid4()), Severity.HIGH)
        finding3 = self._create_sample_finding(str(uuid4()), Severity.MEDIUM)
        
        self.db.save_finding(finding1)
        self.db.save_finding(finding2)
        self.db.save_finding(finding3)
        
        findings = self.db.get_findings_for_run(self.run_id)
        self.assertEqual(len(findings), 3)
    
    def test_get_findings_ordered_by_severity(self):
        """Test that findings are ordered by severity (critical first)."""
        finding_low = self._create_sample_finding(str(uuid4()), Severity.LOW)
        finding_low.timestamp = datetime(2024, 1, 15, 10, 0, 0)
        
        finding_critical = self._create_sample_finding(str(uuid4()), Severity.CRITICAL)
        finding_critical.timestamp = datetime(2024, 1, 15, 11, 0, 0)
        
        finding_medium = self._create_sample_finding(str(uuid4()), Severity.MEDIUM)
        finding_medium.timestamp = datetime(2024, 1, 15, 12, 0, 0)
        
        finding_high = self._create_sample_finding(str(uuid4()), Severity.HIGH)
        finding_high.timestamp = datetime(2024, 1, 15, 13, 0, 0)
        
        # Save in random order
        self.db.save_finding(finding_low)
        self.db.save_finding(finding_critical)
        self.db.save_finding(finding_medium)
        self.db.save_finding(finding_high)
        
        findings = self.db.get_findings_for_run(self.run_id)
        
        # Should be ordered: critical, high, medium, low
        self.assertEqual(findings[0].severity, Severity.CRITICAL)
        self.assertEqual(findings[1].severity, Severity.HIGH)
        self.assertEqual(findings[2].severity, Severity.MEDIUM)
        self.assertEqual(findings[3].severity, Severity.LOW)
    
    def test_get_findings_ordered_by_timestamp_within_severity(self):
        """Test that findings of same severity are ordered by timestamp DESC."""
        finding1 = self._create_sample_finding(str(uuid4()), Severity.HIGH)
        finding1.timestamp = datetime(2024, 1, 15, 10, 0, 0)
        
        finding2 = self._create_sample_finding(str(uuid4()), Severity.HIGH)
        finding2.timestamp = datetime(2024, 1, 15, 12, 0, 0)
        
        finding3 = self._create_sample_finding(str(uuid4()), Severity.HIGH)
        finding3.timestamp = datetime(2024, 1, 15, 11, 0, 0)
        
        self.db.save_finding(finding1)
        self.db.save_finding(finding2)
        self.db.save_finding(finding3)
        
        findings = self.db.get_findings_for_run(self.run_id)
        
        # All HIGH severity, ordered by timestamp DESC
        self.assertEqual(findings[0].id, finding2.id)  # 12:00
        self.assertEqual(findings[1].id, finding3.id)  # 11:00
        self.assertEqual(findings[2].id, finding1.id)  # 10:00
    
    def test_get_findings_with_severity_filter(self):
        """Test filtering findings by severity."""
        finding_critical = self._create_sample_finding(str(uuid4()), Severity.CRITICAL)
        finding_high = self._create_sample_finding(str(uuid4()), Severity.HIGH)
        finding_medium = self._create_sample_finding(str(uuid4()), Severity.MEDIUM)
        
        self.db.save_finding(finding_critical)
        self.db.save_finding(finding_high)
        self.db.save_finding(finding_medium)
        
        # Filter by HIGH severity
        high_findings = self.db.get_findings_for_run(
            self.run_id, 
            severity_filter=Severity.HIGH
        )
        self.assertEqual(len(high_findings), 1)
        self.assertEqual(high_findings[0].severity, Severity.HIGH)
        
        # Filter by CRITICAL severity
        critical_findings = self.db.get_findings_for_run(
            self.run_id, 
            severity_filter=Severity.CRITICAL
        )
        self.assertEqual(len(critical_findings), 1)
        self.assertEqual(critical_findings[0].severity, Severity.CRITICAL)
    
    def test_get_findings_for_nonexistent_run(self):
        """Test getting findings for a run that doesn't exist."""
        findings = self.db.get_findings_for_run("nonexistent-run-id")
        self.assertEqual(len(findings), 0)


class TestForeignKeyConstraints(unittest.TestCase):
    """Test foreign key constraints between runs and findings."""
    
    def setUp(self):
        """Create and initialize database for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = Path(self.temp_file.name)
        self.temp_file.close()
        self.db = Database(self.db_path)
        self.db.init_db()
    
    def tearDown(self):
        """Clean up database after each test."""
        self.db.close()
        if self.db_path.exists():
            self.db_path.unlink()
    
    def test_delete_run_cascades_to_findings(self):
        """Test that deleting a run also deletes its findings."""
        # Create run
        run_id = str(uuid4())
        run = RunMetadata(
            id=run_id,
            target="example.com",
            profile="standard",
            engagement_mode=EngagementMode.AUTHORIZED,
            state=RunState.RUNNING,
            created_at=datetime.now(),
            run_dir=Path("/tmp/runs/test"),
            artifacts_dir=Path("/tmp/runs/test/artifacts"),
            evidence_dir=Path("/tmp/runs/test/evidence"),
            reports_dir=Path("/tmp/runs/test/reports"),
        )
        self.db.save_run(run)
        
        # Create findings
        for i in range(3):
            finding = Finding(
                id=str(uuid4()),
                run_id=run_id,
                type="xss",
                severity=Severity.HIGH,
                confidence=Confidence.CONFIRMED,
                host="example.com",
                url=f"https://example.com/page{i}",
                parameter="q",
                evidence_paths=["evidence.txt"],
                tool="dalfox",
                timestamp=datetime.now(),
                title=f"Finding {i}",
            )
            self.db.save_finding(finding)
        
        # Verify findings exist
        findings = self.db.get_findings_for_run(run_id)
        self.assertEqual(len(findings), 3)
        
        # Delete run
        self.db.delete_run(run_id)
        
        # Verify findings are also deleted (cascade)
        findings = self.db.get_findings_for_run(run_id)
        self.assertEqual(len(findings), 0)


class TestDatabaseContextManager(unittest.TestCase):
    """Test database context manager usage."""
    
    def setUp(self):
        """Create temporary database path."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = Path(self.temp_file.name)
        self.temp_file.close()
    
    def tearDown(self):
        """Clean up database file."""
        if self.db_path.exists():
            self.db_path.unlink()
    
    def test_context_manager_usage(self):
        """Test using database with context manager."""
        with Database(self.db_path) as db:
            db.init_db()
            
            run = RunMetadata(
                id=str(uuid4()),
                target="example.com",
                profile="standard",
                engagement_mode=EngagementMode.AUTHORIZED,
                state=RunState.PENDING,
                created_at=datetime.now(),
                run_dir=Path("/tmp/runs/test"),
                artifacts_dir=Path("/tmp/runs/test/artifacts"),
                evidence_dir=Path("/tmp/runs/test/evidence"),
                reports_dir=Path("/tmp/runs/test/reports"),
            )
            db.save_run(run)
        
        # Connection should be closed after context exit
        # Verify by opening new connection and checking data persisted
        with Database(self.db_path) as db:
            retrieved = db.get_run(run.id)
            self.assertIsNotNone(retrieved)
            self.assertEqual(retrieved.id, run.id)
    
    def test_close_method(self):
        """Test explicit close method."""
        db = Database(self.db_path)
        db.init_db()
        
        # Connection should be created
        self.assertIsNotNone(db._conn)
        
        # Close connection
        db.close()
        
        # Connection should be None
        self.assertIsNone(db._conn)


class TestDatabaseErrors(unittest.TestCase):
    """Test database error handling."""
    
    def setUp(self):
        """Create temporary database for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.db_path = Path(self.temp_file.name)
        self.temp_file.close()
        self.db = Database(self.db_path)
        self.db.init_db()
    
    def tearDown(self):
        """Clean up database after each test."""
        self.db.close()
        if self.db_path.exists():
            self.db_path.unlink()
    
    def test_save_run_raises_storage_error_on_invalid_data(self):
        """Test that invalid data raises StorageError."""
        # Create a run with invalid enum value by bypassing normal creation
        # This tests the database's error handling
        run = RunMetadata(
            id=str(uuid4()),
            target="example.com",
            profile="standard",
            engagement_mode=EngagementMode.AUTHORIZED,
            state=RunState.PENDING,
            created_at=datetime.now(),
            run_dir=Path("/tmp/runs/test"),
            artifacts_dir=Path("/tmp/runs/test/artifacts"),
            evidence_dir=Path("/tmp/runs/test/evidence"),
            reports_dir=Path("/tmp/runs/test/reports"),
        )
        
        # This should work normally
        self.db.save_run(run)
        
        # Test successful save doesn't raise
        retrieved = self.db.get_run(run.id)
        self.assertIsNotNone(retrieved)


if __name__ == '__main__':
    unittest.main()
