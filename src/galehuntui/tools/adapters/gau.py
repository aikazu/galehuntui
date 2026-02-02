"""Gau tool adapter for fetching all URLs from various sources.

gau (Get All URLs) fetches URLs from AlienVault's Open Threat Exchange, the Wayback Machine, 
and Common Crawl for any given domain.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from galehuntui.core.models import (
    Finding,
    Severity,
    Confidence,
    ToolConfig,
    ToolResult,
)
from galehuntui.tools.base import ToolAdapterBase


class GauAdapter(ToolAdapterBase):
    """Adapter for gau (Get All URLs) tool.
    
    gau fetches URLs from multiple sources.
    Output is plain text, one URL per line.
    
    Attributes:
        name: Tool identifier ("gau")
        required: True - Required for reconnaissance
        mode_required: None - Available in all engagement modes
    """
    
    name = "gau"
    required = True
    mode_required = None
    
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> list[str]:
        """Build gau command line arguments.
        
        Args:
            inputs: List containing the target domain(s)
            config: Tool execution configuration
            
        Returns:
            Complete command arguments for gau execution
        """
        cmd = [
            str(self._get_tool_path()),
        ]
        
        # Add any custom arguments from config
        if config.args:
            cmd.extend(config.args)
        
        # Handle input
        if len(inputs) == 1:
            input_path = Path(inputs[0])
            if input_path.exists() and input_path.is_file():
                # Input is a file path - gau doesn't have a direct file input flag
                # but we can handle it in run/stream via stdin or by passing it
                pass
            else:
                # Input is a single domain
                cmd.append(inputs[0])
        
        return cmd
    
    async def run(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> ToolResult:
        """Execute gau with given inputs and configuration.
        
        Args:
            inputs: Target domains to scan
            config: Tool execution configuration
            
        Returns:
            ToolResult containing execution results and output path
            
        Raises:
            ToolNotFoundError: If gau binary is not found
            ToolTimeoutError: If execution exceeds timeout
            ToolExecutionError: If execution fails
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolTimeoutError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"gau not found at {tool_path}")
        
        cmd = self.build_command(inputs, config)
        
        # Prepare stdin input for multiple domains or file input
        stdin_input = None
        if len(inputs) > 1:
            stdin_input = "\n".join(inputs)
        elif len(inputs) == 1:
            input_path = Path(inputs[0])
            if input_path.exists() and input_path.is_file():
                stdin_input = input_path.read_text()
        
        start_time = time.time()
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_input else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**config.env} if config.env else None,
            )
            
            # Communicate with timeout
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(
                        input=stdin_input.encode() if stdin_input else None
                    ),
                    timeout=config.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise ToolTimeoutError(
                    f"gau execution exceeded timeout of {config.timeout}s"
                )
            
            duration = time.time() - start_time
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            
            # Save output to file
            output_path = Path(f"/tmp/gau_output_{uuid4().hex[:8]}.txt")
            output_path.write_text(stdout)
            
            return ToolResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
                output_path=output_path,
            )
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"gau binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"gau execution failed: {e}")
            
    async def stream(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> AsyncIterator[str]:
        """Stream gau output in real-time.
        
        Args:
            inputs: Target domains to scan
            config: Tool execution configuration
            
        Yields:
            URLs from gau as they are produced
            
        Raises:
            ToolNotFoundError: If gau binary is not found
            ToolExecutionError: If execution fails
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"gau not found at {tool_path}")
        
        cmd = self.build_command(inputs, config)
        
        # Prepare stdin input
        stdin_input = None
        if len(inputs) > 1:
            stdin_input = "\n".join(inputs)
        elif len(inputs) == 1:
            input_path = Path(inputs[0])
            if input_path.exists() and input_path.is_file():
                stdin_input = input_path.read_text()
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_input else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**config.env} if config.env else None,
            )
            
            # Send stdin if needed
            if stdin_input and process.stdin:
                process.stdin.write(stdin_input.encode())
                await process.stdin.drain()
                process.stdin.close()
            
            # Stream output line by line
            if process.stdout:
                async for line in process.stdout:
                    decoded_line = line.decode("utf-8", errors="replace").strip()
                    if decoded_line:
                        yield decoded_line
            
            await process.wait()
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"gau binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"gau streaming failed: {e}")
            
    def parse_output(self, raw: str) -> list[Finding]:
        """Parse gau plain text output to normalized findings.
        
        Each line in gau output is a URL.
        
        Args:
            raw: Raw plain text output from gau
            
        Returns:
            List of normalized Finding objects
        """
        findings = []
        lines = raw.strip().split("\n")
        
        for line in lines:
            url = line.strip()
            if not url:
                continue
            
            try:
                # Extract host from URL
                from urllib.parse import urlparse
                parsed_url = urlparse(url)
                host = parsed_url.netloc or parsed_url.path.split("/")[0]
                
                finding = Finding(
                    id=str(uuid4()),
                    run_id="",  # Will be set by pipeline orchestrator
                    type="url",
                    severity=Severity.INFO,
                    confidence=Confidence.CONFIRMED,
                    host=host,
                    url=url,
                    parameter=None,
                    evidence_paths=[],
                    tool=self.name,
                    timestamp=datetime.now(),
                    title=f"URL discovered: {url}",
                    description=f"Found via gau",
                    reproduction_steps=[f"URL discovered using gau: {url}"],
                    remediation=None,
                    references=[],
                )
                findings.append(finding)
            except Exception:
                # Skip malformed entries
                continue
                
        return findings
        
    def get_version(self) -> str:
        """Get gau version.
        
        Returns:
            Version string (e.g., "v2.2.3")
            
        Raises:
            ToolNotFoundError: If gau is not installed
            ToolExecutionError: If version check fails
        """
        import subprocess
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not tool_path.exists():
            raise ToolNotFoundError(f"gau not found at {tool_path}")
        
        try:
            result = subprocess.run(
                [str(tool_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            # Parse version from output
            output = result.stdout.strip() or result.stderr.strip()
            if output:
                # Often output is like "gau version 2.2.3" or just "2.2.3"
                return output.split()[-1]
            
            return "unknown"
            
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("gau version check timed out")
        except Exception as e:
            raise ToolExecutionError(f"Failed to get gau version: {e}")
