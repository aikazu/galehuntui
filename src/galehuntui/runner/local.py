"""Local tool execution runner.

This module provides a Runner implementation that executes security tools
directly on the local system. This is the fallback runner when Docker is
not available or when local execution is preferred.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

from galehuntui.core.exceptions import (
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
)
from galehuntui.core.models import ToolConfig, ToolResult
from galehuntui.runner.base import Runner


class LocalRunner(Runner):
    """Execute tools directly on local system.
    
    Uses tool binaries installed in the tools directory. Provides
    direct execution without container isolation. This is the fallback
    runner when Docker is not available.
    """
    
    def __init__(self, tools_dir: Path, work_dir: Path) -> None:
        """Initialize local runner.
        
        Args:
            tools_dir: Directory containing tool binaries
            work_dir: Working directory for tool execution
        """
        super().__init__(tools_dir, work_dir)
        self.bin_dir = tools_dir / "bin"
    
    async def is_available(self) -> bool:
        """Check if local runner is available.
        
        Returns:
            True if tools bin directory exists
        """
        return self.bin_dir.exists() and self.bin_dir.is_dir()
    
    def _get_tool_path(self, tool_name: str) -> Path:
        """Get path to tool binary.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            Path to tool binary
        """
        return self.bin_dir / tool_name
    
    async def _check_tool_exists(self, tool_name: str) -> bool:
        """Check if tool binary exists and is executable.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if tool exists and is executable
        """
        tool_path = self._get_tool_path(tool_name)
        
        if not tool_path.exists():
            return False
        
        if not tool_path.is_file():
            return False
        
        return os.access(tool_path, os.X_OK)
    
    async def execute(
        self,
        config: ToolConfig,
        input_file: Optional[Path] = None,
        output_file: Optional[Path] = None,
    ) -> ToolResult:
        """Execute tool locally.
        
        Args:
            config: Tool configuration
            input_file: Optional input file to pass to tool
            output_file: Path where tool output should be saved
            
        Returns:
            ToolResult containing execution details and output
            
        Raises:
            ToolNotFoundError: Tool binary not found
            ToolTimeoutError: Tool execution exceeded timeout
            ToolExecutionError: Tool execution failed
        """
        if not await self.is_available():
            raise ToolExecutionError(
                "Local runner not available. Tools directory not found."
            )
        
        if not await self._check_tool_exists(config.name):
            raise ToolNotFoundError(
                f"Tool binary not found: {config.name}. "
                f"Expected at: {self._get_tool_path(config.name)}"
            )
        
        if output_file is None:
            output_file = self.work_dir / f"{config.name}_output.txt"
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = self.build_command(config, input_file, output_file)
        
        try:
            stdout, stderr, exit_code, duration = await self._run_subprocess(
                cmd=cmd,
                timeout=config.timeout,
                env=config.env if config.env else None,
                cwd=self.work_dir,
            )
            
            if output_file.exists():
                output_content = output_file.read_text()
            else:
                output_content = stdout
                output_file.write_text(stdout)
            
            return ToolResult(
                stdout=output_content,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
                output_path=output_file,
            )
            
        except ToolTimeoutError:
            raise
        except ToolExecutionError:
            raise
        except Exception as e:
            raise ToolExecutionError(
                f"Local execution failed for {config.name}: {e}"
            ) from e
    
    def build_command(
        self,
        config: ToolConfig,
        input_file: Optional[Path] = None,
        output_file: Optional[Path] = None,
    ) -> list[str]:
        """Build command line for local tool execution.
        
        Args:
            config: Tool configuration
            input_file: Optional input file path
            output_file: Optional output file path
            
        Returns:
            List of command arguments ready for execution
        """
        tool_path = self._get_tool_path(config.name)
        
        cmd = [str(tool_path)]
        cmd.extend(config.args)
        
        return cmd
