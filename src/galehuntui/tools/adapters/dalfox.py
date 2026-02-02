"""Dalfox tool adapter for XSS scanning.

Dalfox is a fast parameter analysis and XSS scanner, which is based on a 
customizable payload and scanning engine. It supports reflected, stored, 
and DOM-based XSS detection.
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


class DalfoxAdapter(ToolAdapterBase):
    """Adapter for Dalfox XSS scanner.
    
    Dalfox scans for XSS vulnerabilities in web applications.
    Output is in JSON format.
    
    Attributes:
        name: Tool identifier ("dalfox")
        required: False - Optional for XSS scanning
        mode_required: None - Available in all engagement modes
    """
    
    name = "dalfox"
    required = False
    mode_required = None
    
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> list[str]:
        """Build Dalfox command line arguments.
        
        Args:
            inputs: List of URLs to scan
            config: Tool execution configuration
            
        Returns:
            Complete command arguments for Dalfox execution
        """
        cmd = [
            str(self._get_tool_path()),
            "url",            # Default to url subcommand
            "--format", "json",
            "--silence",      # Suppress banner
        ]
        
        # Add timeout if specified
        if config.timeout:
            cmd.extend(["--timeout", str(config.timeout)])
        
        # Add delay if specified (mapping from rate_limit)
        if config.rate_limit:
            # Dalfox uses --delay (ms)
            delay = int(1000 / config.rate_limit)
            cmd.extend(["--delay", str(delay)])
        
        # Handle input
        if len(inputs) == 1:
            input_path = Path(inputs[0])
            if input_path.exists() and input_path.is_file():
                cmd[1] = "file"
                cmd.append(str(input_path))
            else:
                cmd.append(inputs[0])
        else:
            # Multiple inputs - will be passed via pipe to stdin
            cmd[1] = "pipe"
        
        # Add any custom arguments from config
        if config.args:
            cmd.extend(config.args)
        
        return cmd

    async def run(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> ToolResult:
        """Execute Dalfox with given inputs and configuration.
        
        Args:
            inputs: URLs to scan
            config: Tool execution configuration
            
        Returns:
            ToolResult containing execution results and output path
            
        Raises:
            ToolNotFoundError: If Dalfox binary is not found
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
            raise ToolNotFoundError(f"Dalfox not found at {tool_path}")
        
        cmd = self.build_command(inputs, config)
        
        # Prepare stdin input for multiple URLs
        stdin_input = None
        if cmd[1] == "pipe":
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
                    f"Dalfox execution exceeded timeout of {config.timeout}s"
                )
            
            duration = time.time() - start_time
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            
            # Save output to file
            output_path = Path(f"/tmp/dalfox_output_{uuid4().hex[:8]}.jsonl")
            output_path.write_text(stdout)
            
            return ToolResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
                output_path=output_path,
            )
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"Dalfox binary not found: {cmd[0]}")
        except Exception as e:
            if isinstance(e, ToolTimeoutError):
                raise
            raise ToolExecutionError(f"Dalfox execution failed: {e}")

    async def stream(  # type: ignore[override]
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> AsyncIterator[str]:
        """Stream Dalfox output in real-time.
        
        Args:
            inputs: URLs to scan
            config: Tool execution configuration
            
        Yields:
            JSON output from Dalfox as they are produced
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"Dalfox not found at {tool_path}")
        
        cmd = self.build_command(inputs, config)
        
        stdin_input = None
        if cmd[1] == "pipe":
            stdin_input = "\n".join(inputs)
        
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if stdin_input else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**config.env} if config.env else None,
            )
            
            if stdin_input and process.stdin:
                process.stdin.write(stdin_input.encode())
                await process.stdin.drain()
                process.stdin.close()
            
            if process.stdout:
                async for line in process.stdout:
                    decoded_line = line.decode("utf-8", errors="replace").strip()
                    if decoded_line:
                        yield decoded_line
            
            await process.wait()
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"Dalfox binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Dalfox streaming failed: {e}")

    def parse_output(self, raw: str) -> list[Finding]:
        """Parse Dalfox JSON output to normalized findings.
        
        Args:
            raw: Raw JSON Lines output from Dalfox
            
        Returns:
            List of normalized Finding objects
        """
        findings = []
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
        """Convert Dalfox JSON object to Finding object.
        
        Args:
            data: Parsed JSON object from Dalfox output
            
        Returns:
            Finding object or None if conversion fails
        """
        # Dalfox JSON structure check
        # {
        #   "type": "V",
        #   "url": "https://...",
        #   "method": "GET",
        #   "param": "q",
        #   "payload": "...",
        #   "evidence": "...",
        #   "severity": "High",
        #   "confidence": "Confirmed",
        #   "poc": "..."
        # }
        
        # We only care about Vulnerable (V) or Potential (P)
        vuln_type = data.get("type", "")
        if vuln_type not in ["V", "P"]:
            return None
            
        severity_str = data.get("severity", "Medium")
        severity = self._map_severity(severity_str)
        
        confidence_str = data.get("confidence", "Firm")
        confidence = self._map_confidence(confidence_str)
        
        url = data.get("url", "")
        host = url.split("//")[-1].split("/")[0] if "//" in url else url.split("/")[0]
        
        param = data.get("param")
        payload = data.get("payload")
        evidence = data.get("evidence", "")
        poc = data.get("poc", "")
        
        title = f"XSS found via {self.name}"
        if vuln_type == "V":
            title = f"Confirmed XSS found via {self.name}"
        elif vuln_type == "P":
            title = f"Potential XSS found via {self.name}"
            
        description = f"XSS vulnerability detected at {url}. "
        if param:
            description += f"Parameter: {param}. "
        if evidence:
            description += f"Evidence: {evidence}"

        finding = Finding(
            id=str(uuid4()),
            run_id="",
            type="xss",
            severity=severity,
            confidence=confidence,
            host=host,
            url=url,
            parameter=param,
            evidence_paths=[],  # To be populated with artifacts if needed
            tool=self.name,
            timestamp=datetime.now(),
            title=title,
            description=description,
            reproduction_steps=[
                f"URL: {url}",
                f"Method: {data.get('method', 'GET')}",
                f"Parameter: {param}" if param else "No parameter",
                f"Payload: {payload}" if payload else "No payload",
                f"PoC: {poc}" if poc else "No PoC link available"
            ],
            remediation="Ensure all user-supplied input is properly sanitized and encoded before being rendered in the browser. Use Content Security Policy (CSP) to mitigate the impact of XSS vulnerabilities.",
            references=["https://owasp.org/www-community/attacks/xss/"]
        )
        
        return finding

    def _map_severity(self, dalfox_severity: str) -> Severity:
        severity_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
        }
        return severity_map.get(dalfox_severity.lower(), Severity.MEDIUM)

    def _map_confidence(self, dalfox_confidence: str) -> Confidence:
        confidence_map = {
            "confirmed": Confidence.CONFIRMED,
            "firm": Confidence.FIRM,
            "tentative": Confidence.TENTATIVE,
        }
        return confidence_map.get(dalfox_confidence.lower(), Confidence.FIRM)

    def get_version(self) -> str:
        """Get Dalfox version.
        
        Returns:
            Version string
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not tool_path.exists():
            raise ToolNotFoundError(f"Dalfox not found at {tool_path}")
        
        try:
            result = subprocess.run(
                [str(tool_path), "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # Dalfox version output is usually just the version string or includes a banner
            # We'll try to extract it
            output = result.stdout.strip()
            if "v" in output:
                # v2.9.1
                return output.split()[-1]
            return output or "unknown"
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("Dalfox version check timed out")
        except Exception as e:
            raise ToolExecutionError(f"Failed to get Dalfox version: {e}")
