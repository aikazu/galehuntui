"""Database operations for GaleHunTUI.

This module provides SQLite-based persistence for runs and findings.
Uses WAL mode for concurrency and JSON serialization for complex fields.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from galehuntui.core.exceptions import StorageError
from galehuntui.core.models import Finding, PipelineStep, RunMetadata, Severity, Confidence, RunState
from galehuntui.core.constants import StepStatus


class Database:
    """SQLite database manager for GaleHunTUI.
    
    Manages runs and findings with JSON serialization for complex fields.
    Uses WAL (Write-Ahead Logging) mode for improved concurrency.
    """
    
    def __init__(self, db_path: Path):
        """Initialize database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection.
        
        Returns:
            SQLite connection with row factory
        """
        if self._conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._conn.row_factory = sqlite3.Row
            # Enable WAL mode for concurrency
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn
    
    def init_db(self) -> None:
        """Initialize database schema using migrations.
        
        Runs all pending migrations to bring the database up to date.
        
        Raises:
            StorageError: If migration fails
        """
        try:
            from galehuntui.storage.migrations.runner import MigrationRunner
            from galehuntui.storage.migrations import m001_initial_schema, m002_add_steps_table
            
            conn = self._get_connection()
            
            runner = MigrationRunner(self.db_path)
            runner.register(1, "initial_schema", m001_initial_schema.up, m001_initial_schema.down)
            runner.register(2, "add_steps_table", m002_add_steps_table.up, m002_add_steps_table.down)
            
            runner.migrate(conn)
            
        except Exception as e:
            raise StorageError(f"Failed to initialize database: {e}") from e
    
    def save_run(self, run: RunMetadata) -> None:
        """Save or update run metadata.
        
        Args:
            run: RunMetadata object to persist
            
        Raises:
            StorageError: If save operation fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Serialize findings_by_severity dict to JSON
            findings_by_severity_json = json.dumps(run.findings_by_severity)
            
            cursor.execute("""
                INSERT INTO runs (
                    id, target, profile, engagement_mode, state,
                    created_at, started_at, completed_at,
                    total_steps, completed_steps, failed_steps,
                    total_findings, findings_by_severity,
                    run_dir, artifacts_dir, evidence_dir, reports_dir
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    state = excluded.state,
                    started_at = excluded.started_at,
                    completed_at = excluded.completed_at,
                    total_steps = excluded.total_steps,
                    completed_steps = excluded.completed_steps,
                    failed_steps = excluded.failed_steps,
                    total_findings = excluded.total_findings,
                    findings_by_severity = excluded.findings_by_severity
            """, (
                run.id,
                run.target,
                run.profile,
                run.engagement_mode.value,
                run.state.value,
                run.created_at.isoformat(),
                run.started_at.isoformat() if run.started_at else None,
                run.completed_at.isoformat() if run.completed_at else None,
                run.total_steps,
                run.completed_steps,
                run.failed_steps,
                run.total_findings,
                findings_by_severity_json,
                str(run.run_dir),
                str(run.artifacts_dir),
                str(run.evidence_dir),
                str(run.reports_dir),
            ))
            
            conn.commit()
            
        except sqlite3.Error as e:
            raise StorageError(f"Failed to save run {run.id}: {e}") from e
    
    def get_run(self, run_id: str) -> Optional[RunMetadata]:
        """Retrieve run metadata by ID.
        
        Args:
            run_id: Run identifier
            
        Returns:
            RunMetadata object if found, None otherwise
            
        Raises:
            StorageError: If retrieval fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
            row = cursor.fetchone()
            
            if row is None:
                return None
            
            # Deserialize JSON fields
            findings_by_severity = json.loads(row["findings_by_severity"])
            
            # Parse engagement mode from string
            from galehuntui.core.constants import EngagementMode
            engagement_mode = EngagementMode(row["engagement_mode"])
            
            # Parse state from string
            state = RunState(row["state"])
            
            return RunMetadata(
                id=row["id"],
                target=row["target"],
                profile=row["profile"],
                engagement_mode=engagement_mode,
                state=state,
                created_at=datetime.fromisoformat(row["created_at"]),
                started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                total_steps=row["total_steps"],
                completed_steps=row["completed_steps"],
                failed_steps=row["failed_steps"],
                total_findings=row["total_findings"],
                findings_by_severity=findings_by_severity,
                run_dir=Path(row["run_dir"]),
                artifacts_dir=Path(row["artifacts_dir"]),
                evidence_dir=Path(row["evidence_dir"]),
                reports_dir=Path(row["reports_dir"]),
            )
            
        except (sqlite3.Error, ValueError, KeyError) as e:
            raise StorageError(f"Failed to retrieve run {run_id}: {e}") from e
    
    def list_runs(
        self,
        limit: int = 100,
        offset: int = 0,
        state_filter: Optional[RunState] = None
    ) -> list[RunMetadata]:
        """List runs with optional filtering.
        
        Args:
            limit: Maximum number of runs to return
            offset: Number of runs to skip
            state_filter: Filter by run state
            
        Returns:
            List of RunMetadata objects ordered by created_at DESC
            
        Raises:
            StorageError: If query fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM runs"
            params: list = []
            
            if state_filter is not None:
                query += " WHERE state = ?"
                params.append(state_filter.value)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            runs = []
            for row in rows:
                findings_by_severity = json.loads(row["findings_by_severity"])
                from galehuntui.core.constants import EngagementMode
                
                runs.append(RunMetadata(
                    id=row["id"],
                    target=row["target"],
                    profile=row["profile"],
                    engagement_mode=EngagementMode(row["engagement_mode"]),
                    state=RunState(row["state"]),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                    completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                    total_steps=row["total_steps"],
                    completed_steps=row["completed_steps"],
                    failed_steps=row["failed_steps"],
                    total_findings=row["total_findings"],
                    findings_by_severity=findings_by_severity,
                    run_dir=Path(row["run_dir"]),
                    artifacts_dir=Path(row["artifacts_dir"]),
                    evidence_dir=Path(row["evidence_dir"]),
                    reports_dir=Path(row["reports_dir"]),
                ))
            
            return runs
            
        except (sqlite3.Error, ValueError) as e:
            raise StorageError(f"Failed to list runs: {e}") from e
    
    def save_finding(self, finding: Finding) -> None:
        """Save finding to database.
        
        Args:
            finding: Finding object to persist
            
        Raises:
            StorageError: If save operation fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Serialize lists to JSON
            evidence_paths_json = json.dumps(finding.evidence_paths)
            reproduction_steps_json = json.dumps(finding.reproduction_steps)
            references_json = json.dumps(finding.references)
            
            cursor.execute("""
                INSERT INTO findings (
                    id, run_id, type, severity, confidence,
                    host, url, parameter, evidence_paths, tool, timestamp,
                    title, description, reproduction_steps, remediation, refs
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    evidence_paths = excluded.evidence_paths,
                    description = excluded.description,
                    reproduction_steps = excluded.reproduction_steps,
                    remediation = excluded.remediation,
                    refs = excluded.refs
            """, (
                finding.id,
                finding.run_id,
                finding.type,
                finding.severity.value,
                finding.confidence.value,
                finding.host,
                finding.url,
                finding.parameter,
                evidence_paths_json,
                finding.tool,
                finding.timestamp.isoformat(),
                finding.title,
                finding.description,
                reproduction_steps_json,
                finding.remediation,
                references_json,
            ))
            
            conn.commit()
            
        except sqlite3.Error as e:
            raise StorageError(f"Failed to save finding {finding.id}: {e}") from e
    
    def get_findings_for_run(
        self,
        run_id: str,
        severity_filter: Optional[Severity] = None
    ) -> list[Finding]:
        """Get all findings for a run.
        
        Args:
            run_id: Run identifier
            severity_filter: Optional severity filter
            
        Returns:
            List of Finding objects ordered by severity DESC, timestamp DESC
            
        Raises:
            StorageError: If query fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM findings WHERE run_id = ?"
            params: list = [run_id]
            
            if severity_filter is not None:
                query += " AND severity = ?"
                params.append(severity_filter.value)
            
            # Order by severity (critical first) and then by timestamp
            severity_order = "CASE severity " + \
                "WHEN 'critical' THEN 1 " + \
                "WHEN 'high' THEN 2 " + \
                "WHEN 'medium' THEN 3 " + \
                "WHEN 'low' THEN 4 " + \
                "WHEN 'info' THEN 5 " + \
                "END"
            
            query += f" ORDER BY {severity_order}, timestamp DESC"
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            findings = []
            for row in rows:
                # Deserialize JSON fields
                evidence_paths = json.loads(row["evidence_paths"])
                reproduction_steps = json.loads(row["reproduction_steps"])
                references = json.loads(row["refs"])
                
                findings.append(Finding(
                    id=row["id"],
                    run_id=row["run_id"],
                    type=row["type"],
                    severity=Severity(row["severity"]),
                    confidence=Confidence(row["confidence"]),
                    host=row["host"],
                    url=row["url"],
                    parameter=row["parameter"],
                    evidence_paths=evidence_paths,
                    tool=row["tool"],
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    title=row["title"],
                    description=row["description"],
                    reproduction_steps=reproduction_steps,
                    remediation=row["remediation"],
                    references=references,
                ))
            
            return findings
            
        except (sqlite3.Error, ValueError) as e:
            raise StorageError(f"Failed to get findings for run {run_id}: {e}") from e
    
    def delete_run(self, run_id: str) -> bool:
        """Delete run and all associated findings.
        
        Args:
            run_id: Run identifier
            
        Returns:
            True if run was deleted, False if not found
            
        Raises:
            StorageError: If delete operation fails
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM runs WHERE id = ?", (run_id,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            return deleted
            
        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete run {run_id}: {e}") from e
    
    def close(self) -> None:
        """Close database connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def save_step(self, run_id: str, step: PipelineStep) -> None:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO run_steps (
                    run_id, step_name, status, started_at, completed_at,
                    duration, output_path, findings_count, exit_code, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, step_name) DO UPDATE SET
                    status = excluded.status,
                    completed_at = excluded.completed_at,
                    duration = excluded.duration,
                    output_path = excluded.output_path,
                    findings_count = excluded.findings_count,
                    exit_code = excluded.exit_code,
                    error_message = excluded.error_message
            """, (
                run_id,
                step.name,
                step.status.value,
                step.started_at.isoformat() if step.started_at else None,
                step.completed_at.isoformat() if step.completed_at else None,
                step.duration,
                str(step.output_path) if step.output_path else None,
                step.findings_count,
                step.exit_code,
                step.error_message,
            ))
            conn.commit()
            
        except sqlite3.Error as e:
            raise StorageError(f"Failed to save step {step.name} for run {run_id}: {e}") from e
    
    def get_steps(self, run_id: str) -> list[PipelineStep]:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM run_steps WHERE run_id = ?", (run_id,))
            rows = cursor.fetchall()
            
            steps = []
            for row in rows:
                steps.append(PipelineStep(
                    name=row["step_name"],
                    status=StepStatus(row["status"]),
                    started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
                    completed_at=datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None,
                    duration=row["duration"],
                    output_path=Path(row["output_path"]) if row["output_path"] else None,
                    findings_count=row["findings_count"] or 0,
                    exit_code=row["exit_code"],
                    error_message=row["error_message"],
                ))
            
            return steps
            
        except (sqlite3.Error, ValueError) as e:
            raise StorageError(f"Failed to get steps for run {run_id}: {e}") from e
    
    def get_completed_step_names(self, run_id: str) -> set[str]:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT step_name FROM run_steps WHERE run_id = ? AND status = ?",
                (run_id, StepStatus.COMPLETED.value),
            )
            return {row["step_name"] for row in cursor.fetchall()}
            
        except sqlite3.Error as e:
            raise StorageError(f"Failed to get completed steps for run {run_id}: {e}") from e
    
    def delete_steps(self, run_id: str) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM run_steps WHERE run_id = ?", (run_id,))
            deleted = cursor.rowcount > 0
            
            conn.commit()
            return deleted
            
        except sqlite3.Error as e:
            raise StorageError(f"Failed to delete steps for run {run_id}: {e}") from e
