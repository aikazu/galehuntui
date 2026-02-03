"""Artifact and evidence file storage for GaleHunTUI.

This module manages the file system storage of tool outputs, evidence files,
and other artifacts generated during scan runs.
"""

import shutil
from pathlib import Path
from typing import Optional

from galehuntui.core.exceptions import StorageError, ArtifactNotFoundError


class ArtifactStorage:
    """Manages artifact and evidence file storage.
    
    Organizes files by run_id with separate directories for:
    - artifacts: Raw tool outputs
    - evidence: Finding evidence (screenshots, request/response data)
    - reports: Generated reports
    """
    
    def __init__(self, base_dir: Path):
        """Initialize artifact storage.
        
        Args:
            base_dir: Base directory for all run artifacts
                     (typically {project_root}/data/runs/)
        """
        self.base_dir = base_dir
    
    def init_run_directories(self, run_id: str) -> tuple[Path, Path, Path, Path]:
        """Initialize directory structure for a run.
        
        Creates the following structure:
        base_dir/
          {run_id}/
            artifacts/
              {tool_name}/
            evidence/
              screenshots/
              requests/
              responses/
            reports/
        
        Args:
            run_id: Run identifier
            
        Returns:
            Tuple of (run_dir, artifacts_dir, evidence_dir, reports_dir)
            
        Raises:
            StorageError: If directory creation fails
        """
        try:
            run_dir = self.base_dir / run_id
            artifacts_dir = run_dir / "artifacts"
            evidence_dir = run_dir / "evidence"
            reports_dir = run_dir / "reports"
            
            # Create main directories
            run_dir.mkdir(parents=True, exist_ok=True)
            artifacts_dir.mkdir(exist_ok=True)
            reports_dir.mkdir(exist_ok=True)
            
            # Create evidence subdirectories
            evidence_dir.mkdir(exist_ok=True)
            (evidence_dir / "screenshots").mkdir(exist_ok=True)
            (evidence_dir / "requests").mkdir(exist_ok=True)
            (evidence_dir / "responses").mkdir(exist_ok=True)
            
            return run_dir, artifacts_dir, evidence_dir, reports_dir
            
        except OSError as e:
            raise StorageError(f"Failed to create directories for run {run_id}: {e}") from e
    
    def save_artifact(
        self,
        run_id: str,
        tool_name: str,
        content: str | bytes,
        filename: str
    ) -> Path:
        """Save tool output artifact.
        
        Args:
            run_id: Run identifier
            tool_name: Tool that generated the artifact
            content: Artifact content (text or binary)
            filename: Output filename
            
        Returns:
            Path to saved artifact
            
        Raises:
            StorageError: If save operation fails
        """
        try:
            # Create tool-specific directory
            tool_dir = self.base_dir / run_id / "artifacts" / tool_name
            tool_dir.mkdir(parents=True, exist_ok=True)
            
            artifact_path = tool_dir / filename
            
            # Write content
            if isinstance(content, bytes):
                artifact_path.write_bytes(content)
            else:
                artifact_path.write_text(content, encoding="utf-8")
            
            return artifact_path
            
        except OSError as e:
            raise StorageError(
                f"Failed to save artifact {filename} for {tool_name} in run {run_id}: {e}"
            ) from e
    
    def save_evidence(
        self,
        run_id: str,
        evidence_type: str,
        content: str | bytes,
        filename: str
    ) -> Path:
        """Save finding evidence file.
        
        Args:
            run_id: Run identifier
            evidence_type: Type of evidence (screenshots, requests, responses)
            content: Evidence content
            filename: Output filename
            
        Returns:
            Path to saved evidence file (relative to evidence_dir for storage in Finding)
            
        Raises:
            StorageError: If save operation fails
            ValueError: If evidence_type is invalid
        """
        valid_types = {"screenshots", "requests", "responses"}
        if evidence_type not in valid_types:
            raise ValueError(
                f"Invalid evidence_type: {evidence_type}. Must be one of {valid_types}"
            )
        
        try:
            evidence_dir = self.base_dir / run_id / "evidence" / evidence_type
            evidence_dir.mkdir(parents=True, exist_ok=True)
            
            evidence_path = evidence_dir / filename
            
            # Write content
            if isinstance(content, bytes):
                evidence_path.write_bytes(content)
            else:
                evidence_path.write_text(content, encoding="utf-8")
            
            # Return relative path from run directory for storage in Finding
            run_dir = self.base_dir / run_id
            return evidence_path.relative_to(run_dir)
            
        except OSError as e:
            raise StorageError(
                f"Failed to save evidence {filename} of type {evidence_type} in run {run_id}: {e}"
            ) from e
    
    def get_artifact_path(
        self,
        run_id: str,
        tool_name: str,
        filename: str
    ) -> Path:
        """Get path to artifact file.
        
        Args:
            run_id: Run identifier
            tool_name: Tool name
            filename: Artifact filename
            
        Returns:
            Absolute path to artifact
            
        Raises:
            ArtifactNotFoundError: If artifact doesn't exist
        """
        artifact_path = self.base_dir / run_id / "artifacts" / tool_name / filename
        
        if not artifact_path.exists():
            raise ArtifactNotFoundError(
                f"Artifact not found: {tool_name}/{filename} in run {run_id}"
            )
        
        return artifact_path
    
    def get_evidence_path(
        self,
        run_id: str,
        relative_path: str
    ) -> Path:
        """Get absolute path to evidence file from relative path.
        
        Args:
            run_id: Run identifier
            relative_path: Relative path from run directory (stored in Finding)
            
        Returns:
            Absolute path to evidence file
            
        Raises:
            ArtifactNotFoundError: If evidence file doesn't exist
        """
        evidence_path = self.base_dir / run_id / relative_path
        
        if not evidence_path.exists():
            raise ArtifactNotFoundError(
                f"Evidence file not found: {relative_path} in run {run_id}"
            )
        
        return evidence_path
    
    def list_artifacts(
        self,
        run_id: str,
        tool_name: Optional[str] = None
    ) -> list[Path]:
        """List all artifacts for a run.
        
        Args:
            run_id: Run identifier
            tool_name: Optional tool name filter
            
        Returns:
            List of artifact file paths
        """
        artifacts_dir = self.base_dir / run_id / "artifacts"
        
        if not artifacts_dir.exists():
            return []
        
        if tool_name is not None:
            tool_dir = artifacts_dir / tool_name
            if not tool_dir.exists():
                return []
            return sorted(tool_dir.iterdir())
        
        # Return all artifacts across all tools
        artifacts = []
        for tool_dir in artifacts_dir.iterdir():
            if tool_dir.is_dir():
                artifacts.extend(tool_dir.iterdir())
        
        return sorted(artifacts)
    
    def copy_file_to_artifacts(
        self,
        source_path: Path,
        run_id: str,
        tool_name: str,
        filename: Optional[str] = None
    ) -> Path:
        """Copy existing file to artifacts directory.
        
        Useful for moving tool output files from temp directories.
        
        Args:
            source_path: Path to source file
            run_id: Run identifier
            tool_name: Tool name
            filename: Optional destination filename (uses source name if not provided)
            
        Returns:
            Path to copied artifact
            
        Raises:
            StorageError: If copy operation fails
            FileNotFoundError: If source file doesn't exist
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        try:
            tool_dir = self.base_dir / run_id / "artifacts" / tool_name
            tool_dir.mkdir(parents=True, exist_ok=True)
            
            dest_filename = filename or source_path.name
            dest_path = tool_dir / dest_filename
            
            shutil.copy2(source_path, dest_path)
            
            return dest_path
            
        except OSError as e:
            raise StorageError(
                f"Failed to copy file {source_path} to artifacts: {e}"
            ) from e
    
    def delete_run_artifacts(self, run_id: str) -> bool:
        """Delete all artifacts for a run.
        
        Args:
            run_id: Run identifier
            
        Returns:
            True if artifacts were deleted, False if run directory didn't exist
            
        Raises:
            StorageError: If deletion fails
        """
        run_dir = self.base_dir / run_id
        
        if not run_dir.exists():
            return False
        
        try:
            shutil.rmtree(run_dir)
            return True
            
        except OSError as e:
            raise StorageError(
                f"Failed to delete artifacts for run {run_id}: {e}"
            ) from e
    
    def get_run_size(self, run_id: str) -> int:
        """Calculate total size of run artifacts in bytes.
        
        Args:
            run_id: Run identifier
            
        Returns:
            Total size in bytes (0 if run doesn't exist)
        """
        run_dir = self.base_dir / run_id
        
        if not run_dir.exists():
            return 0
        
        total_size = 0
        for file_path in run_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        
        return total_size
    
    def cleanup_old_runs(
        self,
        keep_count: int = 50,
        min_age_days: Optional[int] = None
    ) -> list[str]:
        """Clean up old run artifacts.
        
        Keeps the most recent N runs and optionally removes runs older than X days.
        
        Args:
            keep_count: Number of most recent runs to keep
            min_age_days: Optional minimum age in days for deletion
            
        Returns:
            List of deleted run IDs
            
        Raises:
            StorageError: If cleanup fails
        """
        if not self.base_dir.exists():
            return []
        
        try:
            # Get all run directories sorted by modification time (newest first)
            run_dirs = [
                d for d in self.base_dir.iterdir()
                if d.is_dir()
            ]
            run_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
            
            deleted_runs = []
            
            for idx, run_dir in enumerate(run_dirs):
                should_delete = False
                
                # Keep recent runs
                if idx < keep_count:
                    continue
                
                # Check age if specified
                if min_age_days is not None:
                    import time
                    age_days = (time.time() - run_dir.stat().st_mtime) / 86400
                    if age_days >= min_age_days:
                        should_delete = True
                else:
                    # Delete if beyond keep_count
                    should_delete = True
                
                if should_delete:
                    run_id = run_dir.name
                    shutil.rmtree(run_dir)
                    deleted_runs.append(run_id)
            
            return deleted_runs
            
        except OSError as e:
            raise StorageError(f"Failed to cleanup old runs: {e}") from e
