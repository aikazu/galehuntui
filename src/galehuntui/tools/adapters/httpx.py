"""Httpx tool adapter for HTTP probing and reconnaissance.

Httpx is a fast and multi-purpose HTTP toolkit that allows running multiple probes
using the retryablehttp library. It is used for probing live hosts and gathering
information about web servers, technologies, and response status.
"""

import asyncio
import json
import subprocess
import time
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional
from uuid import uuid4

from galehuntui.core.models import (
    Finding,
    Severity,
    Confidence,
    ToolConfig,
    ToolResult,
)
from galehuntui.tools.base import ToolAdapterBase


class HttpxAdapter(ToolAdapterBase):
    """Adapter for Httpx HTTP toolkit.
    
    Httpx probes URLs to identify live hosts, status codes, titles, and technologies.
    Output is in JSON Lines format.
    
    Attributes:
        name: Tool identifier ("httpx")
        required: True - Required for reconnaissance
        mode_required: None - Available in all engagement modes
    """
    
    name = "httpx"
    required = True
    mode_required = None
    
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> list[str]:
        """Build Httpx command line arguments.
        
        Args:
            inputs: List of URLs/domains to probe, or path to input file
            config: Tool execution configuration
            
        Returns:
            Complete command arguments for Httpx execution
        """
        cmd = [
            str(self._get_tool_path()),
            "-json",          # JSON Lines output format
            "-silent",        # Suppress banner and update messages
        ]
        
        # Add timeout if specified
        if config.timeout:
            # httpx uses -timeout flag in seconds
            cmd.extend(["-timeout", str(config.timeout)])
        
        # Add rate limiting if specified
        if config.rate_limit:
            cmd.extend(["-rate-limit", str(config.rate_limit)])
        
        # Handle input
        if len(inputs) == 1:
            input_path = Path(inputs[0])
            if input_path.exists() and input_path.is_file():
                # Input is a file path
                cmd.extend(["-list", str(input_path)])
            else:
                # Input is a single URL
                cmd.extend(["-u", inputs[0]])
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
        """Execute Httpx with given inputs and configuration.
        
        Args:
            inputs: URLs/domains to probe
            config: Tool execution configuration
            
        Returns:
            ToolResult containing execution results and output path
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolTimeoutError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"Httpx not found at {tool_path}")
        
        cmd = self.build_command(inputs, config)
        
        # Prepare stdin input for multiple URLs
        stdin_input = None
        if len(inputs) > 1 and not (len(inputs) == 1 and Path(inputs[0]).exists()):
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
                    f"Httpx execution exceeded timeout of {config.timeout}s"
                )
            
            duration = time.time() - start_time
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            
            # Save output to file
            output_path = Path(f"/tmp/httpx_output_{uuid4().hex[:8]}.jsonl")
            output_path.write_text(stdout)
            
            return ToolResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
                output_path=output_path,
            )
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"Httpx binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Httpx execution failed: {e}")
    
    async def stream(  # type: ignore[override]
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> AsyncIterator[str]:
        """Stream Httpx output in real-time.
        
        Args:
            inputs: URLs/domains to probe
            config: Tool execution configuration
            
        Yields:
            JSON Lines output from Httpx as they are produced
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"Httpx not found at {tool_path}")
        
        cmd = self.build_command(inputs, config)
        
        # Prepare stdin input
        stdin_input = None
        if len(inputs) > 1 and not (len(inputs) == 1 and Path(inputs[0]).exists()):
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
            raise ToolNotFoundError(f"Httpx binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Httpx streaming failed: {e}")
    
    def parse_output(self, raw: str) -> list[Finding]:
        """Parse Httpx JSON Lines output to normalized findings.
        
        Args:
            raw: Raw JSON Lines output from Httpx
            
        Returns:
            List of normalized Finding objects
        """
        findings = []
        
        # Parse JSON Lines format
        json_objects = self._parse_json_lines(raw)
        
        for data in json_objects:
            try:
                finding = self._convert_to_finding(data)
                if finding:
                    findings.append(finding)
            except (KeyError, ValueError):
                continue
        
        return findings
    
    def _convert_to_finding(self, data: dict) -> Optional[Finding]:
        """Convert Httpx JSON output to Finding object.
        
        Args:
            data: Parsed JSON object from Httpx output
            
        Returns:
            Finding object or None if conversion fails
        """
        url = data.get("url")
        if not url:
            return None
            
        host = data.get("host", "")
        status_code = data.get("status_code")
        title = data.get("title", "No Title")
        webserver = data.get("webserver", "unknown")
        technologies = data.get("technologies", [])
        
        # Build description
        desc_parts = [
            f"Status Code: {status_code}" if status_code else "",
            f"Webserver: {webserver}" if webserver != "unknown" else "",
            f"Technologies: {', '.join(technologies)}" if technologies else "",
        ]
        description = " | ".join(filter(None, desc_parts))
        
        # Parse timestamp
        timestamp_str = data.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now()
        else:
            timestamp = datetime.now()
            
        return Finding(
            id=str(uuid4()),
            run_id="",  # Will be set by pipeline orchestrator
            type="http_probe",
            severity=Severity.INFO,
            confidence=Confidence.CONFIRMED,
            host=host,
            url=url,
            parameter=None,
            evidence_paths=[],
            tool=self.name,
            timestamp=timestamp,
            title=f"Live HTTP Endpoint: {title}",
            description=description,
            reproduction_steps=[f"Probe URL: {url}"],
            remediation=None,
            references=[],
        )
    
    def get_version(self) -> str:
        """Get Httpx version.
        
        Returns:
            Version string
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not tool_path.exists():
            raise ToolNotFoundError(f"Httpx not found at {tool_path}")
        
        try:
            result = subprocess.run(
                [str(tool_path), "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            output = result.stdout.strip()
            if "v" in output:
                version = output.split()[-1]
                return version
            
            return output or "unknown"
            
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("Httpx version check timed out")
        except Exception as e:
            raise ToolExecutionError(f"Failed to get Httpx version: {e}")
