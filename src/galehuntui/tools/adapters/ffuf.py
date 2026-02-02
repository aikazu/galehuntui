"""Ffuf tool adapter for web fuzzing and content discovery.

Ffuf (Fuzz Faster U Fool) is a fast web fuzzer written in Go.
It is used for directory discovery, parameter fuzzing, and virtual host discovery.
"""

import asyncio
import json
import subprocess
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


class FfufAdapter(ToolAdapterBase):
    """Adapter for Ffuf web fuzzer.
    
    Ffuf performs fast web fuzzing to discover hidden directories, files,
    and parameters. Output is in JSON format.
    
    Attributes:
        name: Tool identifier ("ffuf")
        required: False - Optional for fuzzing
        mode_required: "authorized" - Requires authorized mode
    """
    
    name = "ffuf"
    required = False
    mode_required = "authorized"
    
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> list[str]:
        """Build Ffuf command line arguments.
        
        Args:
            inputs: List of URLs to fuzz (should contain FUZZ keyword)
            config: Tool execution configuration
            
        Returns:
            Complete command arguments for Ffuf execution
        """
        cmd = [
            str(self._get_tool_path()),
            "-json",          # JSON output format
            "-s",             # Silent mode (suppress banner)
        ]
        
        # Add timeout if specified (ffuf uses -maxtime in seconds)
        if config.timeout:
            cmd.extend(["-maxtime", str(config.timeout)])
        
        # Add rate limiting if specified (ffuf uses -rate in requests per second)
        if config.rate_limit:
            cmd.extend(["-rate", str(config.rate_limit)])
            
        # Handle input URL
        if inputs:
            url = inputs[0]
            # Handle FUZZ keyword replacement if needed
            if "FUZZ" not in url:
                if url.endswith("/"):
                    url += "FUZZ"
                else:
                    url += "/FUZZ"
            cmd.extend(["-u", url])
            
        # Add any custom arguments from config (including wordlist -w)
        if config.args:
            cmd.extend(config.args)
            
        return cmd

    async def run(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> ToolResult:
        """Execute Ffuf with given inputs and configuration.
        
        Args:
            inputs: URLs to fuzz
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
            raise ToolNotFoundError(f"Ffuf not found at {tool_path}")
        
        cmd = self.build_command(inputs, config)
        
        start_time = time.time()
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**config.env} if config.env else None,
            )
            
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=config.timeout,
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise ToolTimeoutError(
                    f"Ffuf execution exceeded timeout of {config.timeout}s"
                )
            
            duration = time.time() - start_time
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            
            # Save output to file
            output_path = Path(f"/tmp/ffuf_output_{uuid4().hex[:8]}.json")
            output_path.write_text(stdout)
            
            return ToolResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
                output_path=output_path,
            )
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"Ffuf binary not found: {cmd[0]}")
        except Exception as e:
            if isinstance(e, ToolTimeoutError):
                raise
            raise ToolExecutionError(f"Ffuf execution failed: {e}")

    async def stream(  # type: ignore[override]
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> AsyncIterator[str]:
        """Stream Ffuf output in real-time.
        
        Note: Ffuf's JSON output is typically produced at the end.
        This method streams the raw output which might include progress or results.
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"Ffuf not found at {tool_path}")
        
        cmd = self.build_command(inputs, config)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**config.env} if config.env else None,
            )
            
            if process.stdout:
                async for line in process.stdout:
                    decoded_line = line.decode("utf-8", errors="replace").strip()
                    if decoded_line:
                        yield decoded_line
            
            await process.wait()
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"Ffuf binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Ffuf streaming failed: {e}")

    def parse_output(self, raw: str) -> list[Finding]:
        """Parse Ffuf JSON output to normalized findings.
        
        Args:
            raw: Raw JSON output from Ffuf
            
        Returns:
            List of normalized Finding objects
        """
        findings = []
        
        if not raw.strip():
            return findings
            
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and "results" in data:
                for result in data["results"]:
                    finding = self._convert_to_finding(result)
                    if finding:
                        findings.append(finding)
        except json.JSONDecodeError:
            # Fallback to JSON Lines parsing in case of fragmented output
            json_objects = self._parse_json_lines(raw)
            for data in json_objects:
                # ffuf results in JSONL might be just the result object
                finding = self._convert_to_finding(data)
                if finding:
                    findings.append(finding)
        
        return findings

    def _convert_to_finding(self, data: dict) -> Optional[Finding]:
        """Convert Ffuf result to Finding object.
        
        Args:
            data: Parsed JSON object from Ffuf results
            
        Returns:
            Finding object or None if conversion fails
        """
        url = data.get("url")
        if not url:
            return None
            
        status = data.get("status", 0)
        host = data.get("host", "")
        if not host and "//" in url:
            host = url.split("//")[-1].split("/")[0]
            
        content_length = data.get("length", 0)
        words = data.get("words", 0)
        lines = data.get("lines", 0)
        
        # Determine severity based on status code
        severity = Severity.INFO
        if status in [200, 204]:
            severity = Severity.LOW
        elif status in [401, 403]:
            severity = Severity.MEDIUM
            
        title = f"Discovered: {url} (Status: {status})"
        description = (
            f"Ffuf discovered a resource at {url}. "
            f"Status: {status}, Length: {content_length}, Words: {words}, Lines: {lines}"
        )
        
        # Extract inputs
        fuzz_input = data.get("input", {})
        reproduction_steps = [f"Fuzz target: {url}"]
        for key, value in fuzz_input.items():
            reproduction_steps.append(f"Input {key}: {value}")
            
        return Finding(
            id=str(uuid4()),
            run_id="",  # Will be set by pipeline orchestrator
            type="directory_discovery",
            severity=severity,
            confidence=Confidence.CONFIRMED,
            host=host,
            url=url,
            parameter=None,
            evidence_paths=[],
            tool=self.name,
            timestamp=datetime.now(),
            title=title,
            description=description,
            reproduction_steps=reproduction_steps,
            remediation="Ensure that sensitive files and directories are not publicly accessible. Use proper access controls and avoid predictable naming conventions.",
            references=["https://owasp.org/www-project-top-ten/2017/A5_2017-Broken_Access_Control"]
        )

    def get_version(self) -> str:
        """Get Ffuf version.
        
        Returns:
            Version string
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not tool_path.exists():
            raise ToolNotFoundError(f"Ffuf not found at {tool_path}")
            
        try:
            result = subprocess.run(
                [str(tool_path), "-V"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            output = result.stdout.strip() or result.stderr.strip()
            if "version:" in output:
                return output.split("version:")[-1].strip()
            return output or "unknown"
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("Ffuf version check timed out")
        except Exception as e:
            raise ToolExecutionError(f"Failed to get Ffuf version: {e}")
