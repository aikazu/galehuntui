"""Audit logging for compliance and security tracking.

This module provides the AuditLogger class for recording security-sensitive
events during penetration testing runs. All events are logged in JSON Lines
format for easy parsing and analysis.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from galehuntui.core.constants import AuditEventType
from galehuntui.core.exceptions import AuditLogError


class AuditLogger:
    """Audit logger for recording security-sensitive events.
    
    Writes structured events to audit log in JSON Lines format. Each event
    includes timestamp, run_id, event type, and custom details.
    
    Example:
        >>> logger = AuditLogger(run_id="run-123", audit_dir=Path("./runs/run-123"))
        >>> logger.log_event(AuditEventType.RUN_START, {"target": "example.com"})
        >>> logger.close()
    """
    
    def __init__(self, run_id: str, audit_dir: Path) -> None:
        """Initialize audit logger.
        
        Args:
            run_id: Unique identifier for the run.
            audit_dir: Directory where audit log will be stored.
            
        Raises:
            AuditLogError: If audit directory cannot be created.
        """
        self.run_id = run_id
        self.audit_dir = audit_dir
        self.log_path = audit_dir / "audit.log"
        
        try:
            self.audit_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise AuditLogError(
                f"Failed to create audit directory {audit_dir}: {e}"
            ) from e
        
        self._logger = logging.getLogger(f"audit.{run_id}")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False  # Don't propagate to root logger
        self._logger.handlers.clear()
        
        try:
            handler = logging.FileHandler(str(self.log_path), mode="a")
            handler.setLevel(logging.INFO)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
        except Exception as e:
            raise AuditLogError(
                f"Failed to create audit log file {self.log_path}: {e}"
            ) from e
    
    def log_event(
        self,
        event_type: AuditEventType,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log a security-sensitive event.
        
        Args:
            event_type: Type of event being logged.
            details: Optional additional event details.
            
        Raises:
            AuditLogError: If writing to log file fails.
        """
        if details is None:
            details = {}
        
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": self.run_id,
            "event_type": event_type.value,
            "details": details,
        }
        
        try:
            log_line = json.dumps(event, ensure_ascii=False)
            self._logger.info(log_line)
        except Exception as e:
            raise AuditLogError(
                f"Failed to write audit event {event_type.value}: {e}"
            ) from e
    
    def close(self) -> None:
        """Close audit logger and flush buffers."""
        for handler in self._logger.handlers:
            handler.flush()
            handler.close()
        self._logger.handlers.clear()
