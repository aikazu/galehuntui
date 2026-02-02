"""Docker-based tool execution runner.

This module provides a Runner implementation that executes security tools
inside Docker containers. This is the preferred execution method as it
provides isolation, consistent environments, and easier dependency management.
"""

import asyncio
from pathlib import Path
from typing import Optional

from galehuntui.core.exceptions import (
    ToolExecutionError,
    ToolNotFoundError,
    ToolTimeoutError,
)
from galehuntui.core.models import ToolConfig, ToolResult
from galehuntui.runner.base import Runner


TOOL_IMAGES = {
    "subfinder": "projectdiscovery/subfinder:latest",
    "dnsx": "projectdiscovery/dnsx:latest",
    "httpx": "projectdiscovery/httpx:latest",
    "katana": "projectdiscovery/katana:latest",
    "nuclei": "projectdiscovery/nuclei:latest",
    "dalfox": "hahwul/dalfox:latest",
    "ffuf": "ffuf/ffuf:latest",
    "sqlmap": "pberba/sqlmap:latest",
}


class DockerRunner(Runner):
    """Execute tools in Docker containers.
    
    Uses official tool images from Docker Hub. Provides isolation and
    consistent execution environment across different systems.
    """
    
    def __init__(self, tools_dir: Path, work_dir: Path) -> None:
        super().__init__(tools_dir, work_dir)
        self._docker_available: Optional[bool] = None
    
    async def is_available(self) -> bool:
        """Check if Docker is installed and accessible."""
        if self._docker_available is not None:
            return self._docker_available
        
        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            self._docker_available = process.returncode == 0
            return self._docker_available
        except FileNotFoundError:
            self._docker_available = False
            return False
    
    async def execute(
        self,
        config: ToolConfig,
        input_file: Optional[Path] = None,
        output_file: Optional[Path] = None,
    ) -> ToolResult:
        """Execute tool in Docker container."""
        if not await self.is_available():
            raise ToolExecutionError(
                "Docker is not available. Install Docker or use local runner."
            )
        
        if config.name not in TOOL_IMAGES:
            raise ToolNotFoundError(
                f"No Docker image configured for tool: {config.name}"
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
                f"Docker execution failed for {config.name}: {e}"
            ) from e
    
    def build_command(
        self,
        config: ToolConfig,
        input_file: Optional[Path] = None,
        output_file: Optional[Path] = None,
    ) -> list[str]:
        """Build Docker command with volume mounts and tool arguments."""
        image = TOOL_IMAGES[config.name]
        
        cmd = [
            "docker",
            "run",
            "--rm",
            "-i",
        ]
        
        if output_file:
            output_dir = output_file.parent.resolve()
            container_output_dir = Path("/output")
            cmd.extend([
                "-v", f"{output_dir}:{container_output_dir}",
            ])
        
        if input_file:
            input_dir = input_file.parent.resolve()
            container_input_dir = Path("/input")
            container_input_file = container_input_dir / input_file.name
            cmd.extend([
                "-v", f"{input_dir}:{container_input_dir}:ro",
            ])
        
        work_dir_abs = self.work_dir.resolve()
        container_work_dir = Path("/work")
        cmd.extend([
            "-v", f"{work_dir_abs}:{container_work_dir}",
            "-w", str(container_work_dir),
        ])
        
        cmd.append(image)
        
        for arg in config.args:
            if input_file and str(input_file) in arg:
                container_input_file = Path("/input") / input_file.name
                arg = arg.replace(str(input_file), str(container_input_file))
            elif output_file and str(output_file) in arg:
                container_output_file = Path("/output") / output_file.name
                arg = arg.replace(str(output_file), str(container_output_file))
            
            cmd.append(arg)
        
        return cmd
    
    async def pull_image(self, tool_name: str) -> bool:
        """Pull Docker image for a tool.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if pull successful, False otherwise
        """
        if tool_name not in TOOL_IMAGES:
            return False
        
        image = TOOL_IMAGES[tool_name]
        
        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "pull",
                image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False
    
    async def check_image_exists(self, tool_name: str) -> bool:
        """Check if Docker image for tool exists locally.
        
        Args:
            tool_name: Name of the tool
            
        Returns:
            True if image exists locally, False otherwise
        """
        if tool_name not in TOOL_IMAGES:
            return False
        
        image = TOOL_IMAGES[tool_name]
        
        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "image",
                "inspect",
                image,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
            return process.returncode == 0
        except Exception:
            return False
