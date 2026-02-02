"""Wfuzz tool adapter for web application fuzzing.

Wfuzz is a web application fuzzer for discovering hidden resources,
testing parameters, and brute-forcing various application components.
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


class WfuzzAdapter(ToolAdapterBase):
    """Adapter for Wfuzz web application fuzzer.
    
    Wfuzz fuzzes web applications to discover hidden resources, parameters,
    and other application components. Supports various fuzzing modes.
    
    Attributes:
        name: Tool identifier ("wfuzz")
        required: False - Optional for fuzzing
        mode_required: None - Available in all engagement modes
    """
    
    name = "wfuzz"
    required = False
    mode_required = None
    
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> list[str]:
        """Build Wfuzz command line arguments.
        
        Args:
            inputs: List of URLs to fuzz (with FUZZ keyword placeholders)
            config: Tool execution configuration
            
        Returns:
            Complete command arguments for Wfuzz execution
        """
        cmd = [
            str(self._get_tool_path()),
            "-o", "json",  # JSON output format
        ]
        
        # Add timeout if specified (per request)
        if config.timeout:
            # Wfuzz uses --conn-delay and --req-delay
            timeout_per_request = min(config.timeout, 30)
            cmd.extend(["--conn-delay", str(timeout_per_request)])
        
        # Add rate limiting via threads and delay
        if config.rate_limit:
            # Wfuzz uses -t for threads
            threads = min(config.rate_limit, 50)  # Cap at 50 threads
            cmd.extend(["-t", str(threads)])
        
        # Hide common error codes (404, etc.) by default
        cmd.extend(["--hc", "404"])
        
        # Add any custom arguments from config (like -w for wordlist, -z for payload)
        if config.args:
            cmd.extend(config.args)
        
        # Add URL(s) - Wfuzz expects URL at the end
        if len(inputs) >= 1:
            # Wfuzz works on single URL with FUZZ keyword
            cmd.append(inputs[0])
        
        return cmd
    
    async def run(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> ToolResult:
        """Execute Wfuzz with given inputs and configuration.
        
        Args:
            inputs: URLs to fuzz (must contain FUZZ keyword)
            config: Tool execution configuration
            
        Returns:
            ToolResult containing execution results and output path
            
        Raises:
            ToolNotFoundError: If Wfuzz is not found
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
            raise ToolNotFoundError(f"Wfuzz not found at {tool_path}")
        
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
                    f"Wfuzz execution exceeded timeout of {config.timeout}s"
                )
            
            duration = time.time() - start_time
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            
            # Save output to file
            output_path = Path(f"/tmp/wfuzz_output_{uuid4().hex[:8]}.json")
            output_path.write_text(stdout)
            
            return ToolResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
                output_path=output_path,
            )
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"Wfuzz binary not found: {cmd[0]}")
        except Exception as e:
            if isinstance(e, ToolTimeoutError):
                raise
            raise ToolExecutionError(f"Wfuzz execution failed: {e}")
    
    async def stream(  # type: ignore[override]
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> AsyncIterator[str]:
        """Stream Wfuzz output in real-time.
        
        Args:
            inputs: URLs to fuzz
            config: Tool execution configuration
            
        Yields:
            JSON output lines from Wfuzz as they are produced
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"Wfuzz not found at {tool_path}")
        
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
            raise ToolNotFoundError(f"Wfuzz binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Wfuzz streaming failed: {e}")
    
    def parse_output(self, raw: str) -> list[Finding]:
        """Parse Wfuzz JSON output to normalized findings.
        
        Wfuzz outputs results in JSON format when using -o json option.
        Each successful fuzz result is a discovered resource or interesting finding.
        
        Args:
            raw: Raw JSON output from Wfuzz
            
        Returns:
            List of normalized Finding objects
        """
        findings = []
        
        # Wfuzz JSON can be a list of results or JSONL
        try:
            # Try parsing as JSON array first
            data = json.loads(raw)
            if isinstance(data, list):
                for result in data:
                    finding = self._convert_to_finding(result)
                    if finding:
                        findings.append(finding)
            else:
                # Single result
                finding = self._convert_to_finding(data)
                if finding:
                    findings.append(finding)
        except json.JSONDecodeError:
            # Try parsing as JSON Lines
            json_objects = self._parse_json_lines(raw)
            for data in json_objects:
                finding = self._convert_to_finding(data)
                if finding:
                    findings.append(finding)
        
        return findings
    
    def _convert_to_finding(self, data: dict) -> Optional[Finding]:
        """Convert Wfuzz JSON result to Finding object.
        
        Args:
            data: Parsed JSON object from Wfuzz output
            
        Returns:
            Finding object or None
        """
        # Wfuzz JSON structure (approximate):
        # {
        #   "url": "http://example.com/admin",
        #   "code": 200,
        #   "lines": 50,
        #   "words": 500,
        #   "chars": 5000,
        #   "payload": "admin"
        # }
        
        try:
            url = data.get("url", "")
            code = data.get("code", 0)
            payload = data.get("payload", "")
            lines = data.get("lines", 0)
            words = data.get("words", 0)
            chars = data.get("chars", 0)
            
            if not url:
                return None
            
            # Extract host
            host = url.split("//")[-1].split("/")[0] if "//" in url else url.split("/")[0]
            
            # Determine severity based on response code and content
            severity = Severity.INFO
            confidence = Confidence.TENTATIVE
            finding_type = "discovered-resource"
            
            # Interesting responses that might indicate vulnerabilities
            if code == 200:
                severity = Severity.LOW
                confidence = Confidence.FIRM
            elif code in [301, 302, 307, 308]:
                severity = Severity.INFO
                finding_type = "discovered-redirect"
            elif code == 403:
                severity = Severity.LOW
                finding_type = "discovered-forbidden"
                confidence = Confidence.FIRM
            elif code == 401:
                severity = Severity.MEDIUM
                finding_type = "discovered-protected"
                confidence = Confidence.FIRM
            elif code >= 500:
                severity = Severity.MEDIUM
                finding_type = "server-error"
                confidence = Confidence.CONFIRMED
            
            title = f"Resource discovered via {self.name}: {payload}"
            description = f"Fuzzing discovered resource at {url} with HTTP {code}. "
            description += f"Response size: {chars} chars, {lines} lines, {words} words. "
            description += f"Payload used: {payload}"
            
            finding = Finding(
                id=str(uuid4()),
                run_id="",
                type=finding_type,
                severity=severity,
                confidence=confidence,
                host=host,
                url=url,
                parameter=None,
                evidence_paths=[],
                tool=self.name,
                timestamp=datetime.now(),
                title=title,
                description=description,
                reproduction_steps=[
                    f"URL: {url}",
                    f"HTTP Status Code: {code}",
                    f"Payload: {payload}",
                    f"Response: {lines} lines, {words} words, {chars} chars",
                    "Access the URL directly to verify",
                ],
                remediation="Review discovered resources to ensure they should be publicly accessible. Remove or protect sensitive endpoints. Implement proper access controls.",
                references=[
                    "https://owasp.org/www-project-top-ten/2017/A6_2017-Security_Misconfiguration",
                ],
            )
            
            return finding
            
        except (KeyError, ValueError):
            return None
    
    def get_version(self) -> str:
        """Get Wfuzz version.
        
        Returns:
            Version string
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not tool_path.exists():
            raise ToolNotFoundError(f"Wfuzz not found at {tool_path}")
        
        try:
            result = subprocess.run(
                [str(tool_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            # Wfuzz version output format: "Wfuzz 3.1.0"
            output = result.stdout.strip()
            if not output:
                output = result.stderr.strip()
            
            if "wfuzz" in output.lower():
                parts = output.split()
                for i, part in enumerate(parts):
                    if "wfuzz" in part.lower() and i + 1 < len(parts):
                        return parts[i + 1]
            
            return output or "unknown"
            
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("Wfuzz version check timed out")
        except Exception as e:
            raise ToolExecutionError(f"Failed to get Wfuzz version: {e}")
