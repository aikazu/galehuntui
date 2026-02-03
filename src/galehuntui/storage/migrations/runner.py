"""Database migration runner."""

import hashlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class Migration:
    version: int
    name: str
    up: Callable[[sqlite3.Connection], None]
    down: Optional[Callable[[sqlite3.Connection], None]] = None


class MigrationRunner:
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._migrations: list[Migration] = []
    
    def register(
        self,
        version: int,
        name: str,
        up: Callable[[sqlite3.Connection], None],
        down: Optional[Callable[[sqlite3.Connection], None]] = None,
    ) -> None:
        self._migrations.append(Migration(version, name, up, down))
        self._migrations.sort(key=lambda m: m.version)
    
    def _init_tracking_table(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
        """)
        conn.commit()
    
    def current_version(self, conn: sqlite3.Connection) -> int:
        try:
            cursor = conn.execute("SELECT MAX(version) FROM schema_migrations")
            row = cursor.fetchone()
            return row[0] if row and row[0] else 0
        except sqlite3.OperationalError:
            return 0
    
    def pending_migrations(self, conn: sqlite3.Connection) -> list[Migration]:
        current = self.current_version(conn)
        return [m for m in self._migrations if m.version > current]
    
    def migrate(
        self,
        conn: sqlite3.Connection,
        target: Optional[int] = None,
    ) -> list[Migration]:
        self._init_tracking_table(conn)
        current = self.current_version(conn)
        
        if target is None:
            target = max((m.version for m in self._migrations), default=0)
        
        pending = [m for m in self._migrations if current < m.version <= target]
        
        if not pending:
            logger.info("No pending migrations")
            return []
        
        applied = []
        for migration in pending:
            logger.info(f"Applying migration {migration.version}: {migration.name}")
            
            try:
                migration.up(conn)
                
                checksum = hashlib.sha256(
                    f"{migration.version}{migration.name}".encode()
                ).hexdigest()[:16]
                
                conn.execute(
                    """
                    INSERT INTO schema_migrations (version, name, checksum, applied_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (migration.version, migration.name, checksum, datetime.utcnow().isoformat()),
                )
                conn.commit()
                applied.append(migration)
                logger.info(f"Migration {migration.version} applied successfully")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Migration {migration.version} failed: {e}")
                raise
        
        return applied
    
    def rollback(
        self,
        conn: sqlite3.Connection,
        steps: int = 1,
    ) -> list[Migration]:
        self._init_tracking_table(conn)
        current = self.current_version(conn)
        
        rolled_back = []
        for _ in range(steps):
            migration = next(
                (m for m in reversed(self._migrations) if m.version == current),
                None,
            )
            
            if migration is None:
                break
            
            if migration.down is None:
                logger.warning(f"Migration {migration.version} has no rollback")
                break
            
            logger.info(f"Rolling back migration {migration.version}: {migration.name}")
            
            try:
                migration.down(conn)
                conn.execute(
                    "DELETE FROM schema_migrations WHERE version = ?",
                    (migration.version,),
                )
                conn.commit()
                rolled_back.append(migration)
                current = self.current_version(conn)
                logger.info(f"Migration {migration.version} rolled back")
                
            except Exception as e:
                conn.rollback()
                logger.error(f"Rollback of {migration.version} failed: {e}")
                raise
        
        return rolled_back
