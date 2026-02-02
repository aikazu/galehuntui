"""Dnsx tool adapter for DNS resolution.

Dnsx is a fast and multi-purpose DNS toolkit allow to run multiple DNS queries.
It supports multiple DNS resolution, brute force, and validation.
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


class DnsxAdapter(ToolAdapterBase):
    """Adapter for Dnsx DNS resolution tool.
    
    Dnsx performs DNS resolution and validation.
    Output is in JSON Lines format.
    
    Attributes:
        name: Tool identifier ("dnsx")
        required: True - Required for DNS resolution
        mode_required: None - Available in all engagement modes
    """
    
    name = "dnsx"
    required = True
    mode_required = None
    
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> list[str]:
        """Build Dnsx command line arguments.
        
        Args:
            inputs: List of domains to resolve, or path to input file
            config: Tool execution configuration
            
        Returns:
            Complete command arguments for Dnsx execution
        """
        cmd = [
            str(self._get_tool_path()),
            "-json",          # JSON Lines output format
            "-silent",        # Suppress banner and update messages
        ]
        
        # Add timeout if specified
        if config.timeout:
            cmd.extend(["-timeout", str(config.timeout)])
        
        # Handle input
        if len(inputs) == 1:
            input_path = Path(inputs[0])
            if input_path.exists() and input_path.is_file():
                # Input is a file path
                cmd.extend(["-l", str(input_path)])
            else:
                # Input is a single domain - will be passed via stdin
                pass
        else:
            # Multiple inputs - will be passed via stdin
            pass
            
        # Add any custom arguments from config
        if config.args:
            cmd.extend(config.args)
        
        return cmd

    async def run(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> ToolResult:
        """Execute Dnsx with given inputs and configuration.
        
        Args:
            inputs: Domains to resolve
            config: Tool execution configuration
            
        Returns:
            ToolResult containing execution results and output path
            
        Raises:
            ToolNotFoundError: If Dnsx binary is not found
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
            raise ToolNotFoundError(f"Dnsx not found at {tool_path}")
        
        cmd = self.build_command(inputs, config)
        
        # Prepare stdin input
        stdin_input = None
        if len(inputs) > 1 or (len(inputs) == 1 and not Path(inputs[0]).exists()):
            stdin_input = "\n".join(inputs)
        
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
                    f"Dnsx execution exceeded timeout of {config.timeout}s"
                )
            
            duration = time.time() - start_time
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            
            # Save output to file
            output_path = Path(f"/tmp/dnsx_output_{uuid4().hex[:8]}.jsonl")
            output_path.write_text(stdout)
            
            return ToolResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
                output_path=output_path,
            )
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"Dnsx binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Dnsx execution failed: {e}")

    async def stream(  # type: ignore
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> AsyncIterator[str]:
        """Stream Dnsx output in real-time.
        
        Args:
            inputs: Domains to resolve
            config: Tool execution configuration
            
        Yields:
            JSON Lines output from Dnsx as they are produced
            
        Raises:
            ToolNotFoundError: If Dnsx binary is not found
            ToolExecutionError: If execution fails
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"Dnsx not found at {tool_path}")
        
        cmd = self.build_command(inputs, config)
        
        # Prepare stdin input
        stdin_input = None
        if len(inputs) > 1 or (len(inputs) == 1 and not Path(inputs[0]).exists()):
            stdin_input = "\n".join(inputs)
        
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
            raise ToolNotFoundError(f"Dnsx binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Dnsx streaming failed: {e}")

    def parse_output(self, raw: str) -> list[Finding]:
        """Parse Dnsx JSON Lines output to normalized findings.
        
        Dnsx output format:
        {"host":"example.com","a":["93.184.216.34"],"status_code":"NOERROR","timestamp":"2024-01-01T12:00:00Z"}
        
        Args:
            raw: Raw JSON Lines output from Dnsx
            
        Returns:
            List of normalized Finding objects
        """
        findings = []
        json_objects = self._parse_json_lines(raw)
        
        for data in json_objects:
            try:
                host = data.get("host")
                if not host:
                    continue
                
                # Get IP from 'a' list or 'ip' field
                ip = None
                a_records = data.get("a", [])
                if a_records and isinstance(a_records, list):
                    ip = a_records[0]
                else:
                    ip = data.get("ip")
                
                timestamp_str = data.get("timestamp")
                if timestamp_str:
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        timestamp = datetime.now()
                else:
                    timestamp = datetime.now()
                
                finding = Finding(
                    id=str(uuid4()),
                    run_id="",  # Will be set by pipeline orchestrator
                    type="dns_resolution",
                    severity=Severity.INFO,
                    confidence=Confidence.CONFIRMED,
                    host=host,
                    url=host,
                    parameter=None,
                    evidence_paths=[],
                    tool=self.name,
                    timestamp=timestamp,
                    title=f"DNS resolved: {host} -> {ip}" if ip else f"DNS resolved: {host}",
                    description=f"Resolved IP: {ip}" if ip else "Resolved via DNS",
                    reproduction_steps=[f"Resolved {host} using dnsx"],
                    remediation=None,
                    references=[],
                )
                findings.append(finding)
            except Exception:
                # Skip malformed entries
                continue
                
        return findings
        
    def get_version(self) -> str:
        """Get Dnsx version.
        
        Returns:
            Version string (e.g., "v1.1.6")
            
        Raises:
            ToolNotFoundError: If Dnsx is not installed
            ToolExecutionError: If version check fails
        """
        import subprocess
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not tool_path.exists():
            raise ToolNotFoundError(f"Dnsx not found at {tool_path}")
        
        try:
            result = subprocess.run(
                [str(tool_path), "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            # Parse version from output (format: "dnsx v1.1.6")
            output = result.stdout.strip()
            if "v" in output:
                version = output.split()[-1]
                return version
            
            return output or "unknown"
            
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("Dnsx version check timed out")
        except Exception as e:
            raise ToolExecutionError(f"Failed to get Dnsx version: {e}")
