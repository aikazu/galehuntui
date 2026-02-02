"""Base runner interface for tool execution.

This module defines the abstract Runner class that all execution backends
must implement. Runners handle the actual execution of security tools,
whether locally, in containers, or remotely.
"""

import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from galehuntui.core.models import ToolConfig, ToolResult


class Runner(ABC):
    """Abstract base class for tool execution runners.
    
    Runners are responsible for executing security tools in different
    environments (local, Docker, remote). All runners must implement
    availability checking and async execution.
    """
    
    def __init__(self, tools_dir: Path, work_dir: Path) -> None:
        """Initialize runner with required directories.
        
        Args:
            tools_dir: Directory containing tool binaries/scripts
            work_dir: Working directory for tool execution (inputs/outputs)
        """
        self.tools_dir = tools_dir
        self.work_dir = work_dir
    
    @abstractmethod
    async def is_available(self) -> bool:
        """Check if runner is available and functional.
        
        Returns:
            True if runner can execute tools, False otherwise
        """
        pass
    
    @abstractmethod
    async def execute(
        self,
        config: ToolConfig,
        input_file: Optional[Path] = None,
        output_file: Optional[Path] = None,
    ) -> ToolResult:
        """Execute a tool with given configuration.
        
        Args:
            config: Tool configuration (name, args, timeout, etc.)
            input_file: Optional input file to pass to tool
            output_file: Path where tool output should be saved
            
        Returns:
            ToolResult containing execution details and output
            
        Raises:
            ToolNotFoundError: Tool binary/image not found
            ToolTimeoutError: Tool execution exceeded timeout
            ToolExecutionError: Tool execution failed
        """
        pass
    
    @abstractmethod
    def build_command(
        self,
        config: ToolConfig,
        input_file: Optional[Path] = None,
        output_file: Optional[Path] = None,
    ) -> list[str]:
        """Build command line arguments for tool execution.
        
        Args:
            config: Tool configuration
            input_file: Optional input file path
            output_file: Optional output file path
            
        Returns:
            List of command arguments ready for execution
        """
        pass
    
    async def _run_subprocess(
        self,
        cmd: list[str],
        timeout: int,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[Path] = None,
    ) -> tuple[str, str, int, float]:
        """Run subprocess and capture output.
        
        Args:
            cmd: Command and arguments to execute
            timeout: Timeout in seconds
            env: Environment variables for subprocess
            cwd: Working directory for subprocess
            
        Returns:
            Tuple of (stdout, stderr, exit_code, duration)
            
        Raises:
            ToolTimeoutError: Process exceeded timeout
            ToolExecutionError: Process execution failed
        """
        from time import time
        from galehuntui.core.exceptions import ToolTimeoutError, ToolExecutionError
        
        start_time = time()
        process = None
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
            )
            
            # Wait for process with timeout
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )
            
            duration = time() - start_time
            exit_code = process.returncode or 0
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            
            return stdout, stderr, exit_code, duration
            
        except asyncio.TimeoutError as e:
            # Kill the process if it times out
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            
            duration = time() - start_time
            raise ToolTimeoutError(
                f"Tool execution exceeded timeout of {timeout}s"
            ) from e
            
        except Exception as e:
            duration = time() - start_time
            raise ToolExecutionError(f"Failed to execute tool: {e}") from e
