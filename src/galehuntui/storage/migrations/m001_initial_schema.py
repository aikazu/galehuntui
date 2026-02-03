"""Migration 001: Initial schema.

Creates the base tables for runs and findings.
"""

import sqlite3


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            target TEXT NOT NULL,
            profile TEXT NOT NULL,
            engagement_mode TEXT NOT NULL,
            state TEXT NOT NULL,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            total_steps INTEGER DEFAULT 0,
            completed_steps INTEGER DEFAULT 0,
            failed_steps INTEGER DEFAULT 0,
            total_findings INTEGER DEFAULT 0,
            findings_by_severity TEXT DEFAULT '{}',
            run_dir TEXT NOT NULL,
            artifacts_dir TEXT NOT NULL,
            evidence_dir TEXT NOT NULL,
            reports_dir TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS findings (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            type TEXT NOT NULL,
            severity TEXT NOT NULL,
            confidence TEXT NOT NULL,
            host TEXT NOT NULL,
            url TEXT NOT NULL,
            parameter TEXT,
            evidence_paths TEXT NOT NULL,
            tool TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            reproduction_steps TEXT DEFAULT '[]',
            remediation TEXT,
            refs TEXT DEFAULT '[]',
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_findings_run_id 
        ON findings(run_id)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_findings_severity 
        ON findings(severity)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_runs_state 
        ON runs(state)
    """)


def down(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS findings")
    cursor.execute("DROP TABLE IF EXISTS runs")
