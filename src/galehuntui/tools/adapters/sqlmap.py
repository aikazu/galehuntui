"""SQLMap tool adapter for SQL injection testing.

SQLMap is an automatic SQL injection and database takeover tool.
It supports detection and exploitation of SQL injection vulnerabilities.
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


class SqlmapAdapter(ToolAdapterBase):
    """Adapter for SQLMap SQL injection scanner.
    
    SQLMap detects and exploits SQL injection vulnerabilities in web applications.
    Output is typically in text format with optional JSON logging.
    
    Attributes:
        name: Tool identifier ("sqlmap")
        required: False - Optional for SQL injection testing
        mode_required: "AUTHORIZED" - Requires authorized engagement mode
    """
    
    name = "sqlmap"
    required = False
    mode_required = "AUTHORIZED"
    
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> list[str]:
        """Build SQLMap command line arguments.
        
        Args:
            inputs: List of URLs to test
            config: Tool execution configuration
            
        Returns:
            Complete command arguments for SQLMap execution
        """
        cmd = [
            str(self._get_tool_path()),
            "--batch",           # Never ask for user input
            "--random-agent",    # Use random User-Agent
            "--output-dir=/tmp/sqlmap",  # Output directory
        ]
        
        # Add timeout if specified
        if config.timeout:
            cmd.extend(["--timeout", str(config.timeout)])
        
        # Add threads for performance (mapping from rate_limit)
        if config.rate_limit:
            threads = min(config.rate_limit, 10)  # Cap at 10 threads
            cmd.extend(["--threads", str(threads)])
        
        # Handle input - SQLMap works on single URLs
        if len(inputs) >= 1:
            input_path = Path(inputs[0])
            if input_path.exists() and input_path.is_file():
                # Input is a file with URLs (bulk scan)
                cmd.extend(["-m", str(input_path)])
            else:
                # Single URL
                cmd.extend(["-u", inputs[0]])
        
        # Add any custom arguments from config
        if config.args:
            cmd.extend(config.args)
        
        return cmd
    
    async def run(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> ToolResult:
        """Execute SQLMap with given inputs and configuration.
        
        Args:
            inputs: URLs to test for SQL injection
            config: Tool execution configuration
            
        Returns:
            ToolResult containing execution results and output path
            
        Raises:
            ToolNotFoundError: If SQLMap is not found
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
            raise ToolNotFoundError(f"SQLMap not found at {tool_path}")
        
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
                    f"SQLMap execution exceeded timeout of {config.timeout}s"
                )
            
            duration = time.time() - start_time
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            
            # Save output to file
            output_path = Path(f"/tmp/sqlmap_output_{uuid4().hex[:8]}.txt")
            output_path.write_text(stdout)
            
            return ToolResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
                output_path=output_path,
            )
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"SQLMap binary not found: {cmd[0]}")
        except Exception as e:
            if isinstance(e, ToolTimeoutError):
                raise
            raise ToolExecutionError(f"SQLMap execution failed: {e}")
    
    async def stream(  # type: ignore[override]
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> AsyncIterator[str]:
        """Stream SQLMap output in real-time.
        
        Args:
            inputs: URLs to test
            config: Tool execution configuration
            
        Yields:
            Output lines from SQLMap as they are produced
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"SQLMap not found at {tool_path}")
        
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
            raise ToolNotFoundError(f"SQLMap binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"SQLMap streaming failed: {e}")
    
    def parse_output(self, raw: str) -> list[Finding]:
        """Parse SQLMap text output to normalized findings.
        
        SQLMap output is primarily text-based with markers for vulnerabilities.
        We look for vulnerability indicators in the output.
        
        Args:
            raw: Raw text output from SQLMap
            
        Returns:
            List of normalized Finding objects
        """
        findings = []
        
        # Parse SQLMap text output for vulnerability markers
        lines = raw.split("\n")
        
        current_url = ""
        current_param = ""
        current_injection_type = ""
        
        for line in lines:
            line = line.strip()
            
            # Extract URL being tested
            if "testing URL" in line.lower() or "target URL:" in line.lower():
                parts = line.split("'")
                if len(parts) >= 2:
                    current_url = parts[1]
            
            # Extract parameter being tested
            if "parameter:" in line.lower():
                parts = line.split("'")
                if len(parts) >= 2:
                    current_param = parts[1]
            
            # Detect vulnerability
            if "vulnerable" in line.lower() or "injectable" in line.lower():
                if current_url:
                    finding = self._create_finding_from_detection(
                        url=current_url,
                        parameter=current_param,
                        detection_line=line,
                    )
                    if finding:
                        findings.append(finding)
        
        return findings
    
    def _create_finding_from_detection(
        self,
        url: str,
        parameter: str,
        detection_line: str,
    ) -> Optional[Finding]:
        """Create Finding object from SQLMap detection.
        
        Args:
            url: Target URL
            parameter: Vulnerable parameter
            detection_line: Detection line from output
            
        Returns:
            Finding object or None
        """
        # Extract host from URL
        host = url.split("//")[-1].split("/")[0] if "//" in url else url.split("/")[0]
        
        # Determine injection type from detection line
        injection_type = "sqli"
        severity = Severity.HIGH
        confidence = Confidence.FIRM
        
        if "time-based blind" in detection_line.lower():
            injection_type = "sqli-time-blind"
        elif "boolean-based blind" in detection_line.lower():
            injection_type = "sqli-boolean-blind"
        elif "error-based" in detection_line.lower():
            injection_type = "sqli-error"
            confidence = Confidence.CONFIRMED
        elif "union query" in detection_line.lower():
            injection_type = "sqli-union"
            severity = Severity.CRITICAL
            confidence = Confidence.CONFIRMED
        
        title = f"SQL Injection ({injection_type}) found via {self.name}"
        description = f"SQL injection vulnerability detected at {url}"
        if parameter:
            description += f" in parameter '{parameter}'"
        description += f". Detection: {detection_line}"
        
        finding = Finding(
            id=str(uuid4()),
            run_id="",
            type=injection_type,
            severity=severity,
            confidence=confidence,
            host=host,
            url=url,
            parameter=parameter if parameter else None,
            evidence_paths=[],
            tool=self.name,
            timestamp=datetime.now(),
            title=title,
            description=description,
            reproduction_steps=[
                f"URL: {url}",
                f"Parameter: {parameter}" if parameter else "No specific parameter",
                f"Detection: {detection_line}",
                "Run SQLMap manually for detailed exploitation",
            ],
            remediation="Use parameterized queries (prepared statements) for all database queries. Never concatenate user input directly into SQL statements. Implement proper input validation and sanitization.",
            references=[
                "https://owasp.org/www-community/attacks/SQL_Injection",
                "https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html",
            ],
        )
        
        return finding
    
    def get_version(self) -> str:
        """Get SQLMap version.
        
        Returns:
            Version string
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not tool_path.exists():
            raise ToolNotFoundError(f"SQLMap not found at {tool_path}")
        
        try:
            result = subprocess.run(
                [str(tool_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            # SQLMap version output format: "sqlmap/1.7.x"
            output = result.stdout.strip()
            if "sqlmap" in output.lower():
                return output.split("/")[-1] if "/" in output else output
            return output or "unknown"
            
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("SQLMap version check timed out")
        except Exception as e:
            raise ToolExecutionError(f"Failed to get SQLMap version: {e}")
