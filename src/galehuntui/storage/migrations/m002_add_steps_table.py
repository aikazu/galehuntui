"""Migration 002: Add run_steps table for resume capability.

Tracks individual step progress for run resume functionality.
"""

import sqlite3


def up(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE run_steps (
            run_id TEXT NOT NULL,
            step_name TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            duration REAL,
            output_path TEXT,
            findings_count INTEGER DEFAULT 0,
            exit_code INTEGER,
            error_message TEXT,
            PRIMARY KEY (run_id, step_name),
            FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("""
        CREATE INDEX idx_run_steps_run_id ON run_steps(run_id)
    """)
    
    cursor.execute("""
        CREATE INDEX idx_run_steps_status ON run_steps(status)
    """)


def down(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS run_steps")
