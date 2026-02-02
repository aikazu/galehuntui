"""Nuclei tool adapter for vulnerability scanning.

Nuclei is a fast and customizable vulnerability scanner based on simple YAML templates.
It supports scanning for a wide range of security issues using community templates.
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


class NucleiAdapter(ToolAdapterBase):
    """Adapter for Nuclei vulnerability scanner.
    
    Nuclei runs templates against targets to identify security vulnerabilities,
    misconfigurations, and known CVEs. Output is in JSON Lines format.
    
    Attributes:
        name: Tool identifier ("nuclei")
        required: True - Required for vulnerability scanning
        mode_required: None - Available in all engagement modes
    """
    
    name = "nuclei"
    required = True
    mode_required = None
    
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> list[str]:
        """Build Nuclei command line arguments.
        
        Args:
            inputs: List of URLs/domains to scan, or path to input file
            config: Tool execution configuration
            
        Returns:
            Complete command arguments for Nuclei execution
            
        Example:
            >>> adapter.build_command(
            ...     inputs=["https://example.com"],
            ...     config=ToolConfig(name="nuclei", timeout=300)
            ... )
            ["/tools/bin/nuclei", "-json", "-silent", "-u", "https://example.com"]
        """
        cmd = [
            str(self._get_tool_path()),
            "-json",          # JSON Lines output format
            "-silent",        # Suppress banner and update messages
        ]
        
        # Add timeout if specified
        if config.timeout:
            cmd.extend(["-timeout", str(config.timeout)])
        
        # Add rate limiting if specified
        if config.rate_limit:
            cmd.extend(["-rate-limit", str(config.rate_limit)])
        
        # Handle input - either single URL, multiple URLs via stdin, or input file
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
            # Nuclei reads from stdin when no -u or -list is provided
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
        """Execute Nuclei with given inputs and configuration.
        
        Args:
            inputs: URLs/domains to scan
            config: Tool execution configuration
            
        Returns:
            ToolResult containing execution results and output path
            
        Raises:
            ToolNotFoundError: If Nuclei binary is not found
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
            raise ToolNotFoundError(f"Nuclei not found at {tool_path}")
        
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
                    f"Nuclei execution exceeded timeout of {config.timeout}s"
                )
            
            duration = time.time() - start_time
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            
            # Save output to file
            output_path = Path(f"/tmp/nuclei_output_{uuid4().hex[:8]}.jsonl")
            output_path.write_text(stdout)
            
            return ToolResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
                output_path=output_path,
            )
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"Nuclei binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Nuclei execution failed: {e}")
    
    async def stream(  # type: ignore[override]
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> AsyncIterator[str]:
        """Stream Nuclei output in real-time.
        
        Args:
            inputs: URLs/domains to scan
            config: Tool execution configuration
            
        Yields:
            JSON Lines output from Nuclei as they are produced
            
        Raises:
            ToolNotFoundError: If Nuclei binary is not found
            ToolTimeoutError: If execution exceeds timeout
            ToolExecutionError: If execution fails
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"Nuclei not found at {tool_path}")
        
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
            raise ToolNotFoundError(f"Nuclei binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Nuclei streaming failed: {e}")
    
    def parse_output(self, raw: str) -> list[Finding]:
        """Parse Nuclei JSON Lines output to normalized findings.
        
        Nuclei output format (one JSON object per line):
        {
            "template-id": "CVE-2021-12345",
            "info": {
                "name": "Vulnerability Name",
                "description": "Description text",
                "severity": "high",
                "tags": ["cve", "..."],
                "reference": ["https://..."]
            },
            "type": "http",
            "host": "https://example.com",
            "matched-at": "https://example.com/path",
            "extracted-results": [...],
            "timestamp": "2024-01-01T12:00:00Z"
        }
        
        Args:
            raw: Raw JSON Lines output from Nuclei
            
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
            except (KeyError, ValueError) as e:
                # Log malformed entries but continue processing
                # In production, this should use proper logging
                continue
        
        return findings
    
    def _convert_to_finding(self, data: dict) -> Optional[Finding]:
        """Convert Nuclei JSON output to Finding object.
        
        Args:
            data: Parsed JSON object from Nuclei output
            
        Returns:
            Finding object or None if conversion fails
        """
        # Extract basic fields
        template_id = data.get("template-id", "unknown")
        info = data.get("info", {})
        
        # Map Nuclei severity to our Severity enum
        nuclei_severity = info.get("severity", "info").lower()
        severity = self._map_severity(nuclei_severity)
        
        # Extract URLs and host
        host = data.get("host", "")
        matched_at = data.get("matched-at", data.get("matched", ""))
        url = matched_at or host
        
        # Parse timestamp
        timestamp_str = data.get("timestamp")
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                timestamp = datetime.now()
        else:
            timestamp = datetime.now()
        
        # Build evidence paths (will be populated later with actual evidence)
        evidence_paths = []
        
        # Extract metadata
        title = info.get("name", template_id)
        description = info.get("description")
        references = info.get("reference", [])
        if isinstance(references, str):
            references = [references]
        
        # Determine confidence based on template type and verification
        confidence = self._determine_confidence(data)
        
        # Create Finding object
        finding = Finding(
            id=str(uuid4()),
            run_id="",  # Will be set by pipeline orchestrator
            type=template_id,
            severity=severity,
            confidence=confidence,
            host=host,
            url=url,
            parameter=None,  # Nuclei doesn't provide parameter info
            evidence_paths=evidence_paths,
            tool=self.name,
            timestamp=timestamp,
            title=title,
            description=description,
            reproduction_steps=self._extract_reproduction_steps(data),
            remediation=info.get("remediation"),
            references=references,
        )
        
        return finding
    
    def _map_severity(self, nuclei_severity: str) -> Severity:
        """Map Nuclei severity to our Severity enum.
        
        Nuclei severities: critical, high, medium, low, info, unknown
        
        Args:
            nuclei_severity: Nuclei severity string
            
        Returns:
            Mapped Severity enum value
        """
        severity_map = {
            "critical": Severity.CRITICAL,
            "high": Severity.HIGH,
            "medium": Severity.MEDIUM,
            "low": Severity.LOW,
            "info": Severity.INFO,
            "unknown": Severity.INFO,
        }
        return severity_map.get(nuclei_severity.lower(), Severity.INFO)
    
    def _determine_confidence(self, data: dict) -> Confidence:
        """Determine finding confidence based on Nuclei output.
        
        Args:
            data: Nuclei JSON output
            
        Returns:
            Confidence level (CONFIRMED, FIRM, or TENTATIVE)
        """
        # If there are extracted results, it's confirmed
        if data.get("extracted-results"):
            return Confidence.CONFIRMED
        
        # If matcher-name indicates verification, it's confirmed
        matcher_name = data.get("matcher-name", "").lower()
        if any(keyword in matcher_name for keyword in ["verified", "exploit", "rce"]):
            return Confidence.CONFIRMED
        
        # Check template type - some types are more reliable
        template_type = data.get("type", "")
        info = data.get("info", {})
        tags = info.get("tags", [])
        
        # CVE detections are generally firm
        if "cve" in tags or template_type == "cve":
            return Confidence.FIRM
        
        # Default to tentative for generic detections
        return Confidence.TENTATIVE
    
    def _extract_reproduction_steps(self, data: dict) -> list[str]:
        """Extract reproduction steps from Nuclei output.
        
        Args:
            data: Nuclei JSON output
            
        Returns:
            List of reproduction steps
        """
        steps = []
        
        # Add matched URL as first step
        matched_at = data.get("matched-at", data.get("matched"))
        if matched_at:
            steps.append(f"Navigate to: {matched_at}")
        
        # Add matcher information if available
        matcher_name = data.get("matcher-name")
        if matcher_name:
            steps.append(f"Matcher triggered: {matcher_name}")
        
        # Add extracted results if available
        extracted = data.get("extracted-results")
        if extracted:
            steps.append(f"Extracted data: {', '.join(map(str, extracted[:3]))}")
        
        return steps
    
    def get_version(self) -> str:
        """Get Nuclei version.
        
        Returns:
            Version string (e.g., "v3.1.0")
            
        Raises:
            ToolNotFoundError: If Nuclei is not installed
            ToolExecutionError: If version check fails
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not tool_path.exists():
            raise ToolNotFoundError(f"Nuclei not found at {tool_path}")
        
        try:
            result = subprocess.run(
                [str(tool_path), "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            # Parse version from output (format: "Nuclei v3.1.0")
            output = result.stdout.strip()
            if "v" in output:
                # Extract version number
                version = output.split()[-1]  # Get last word which is version
                return version
            
            return output or "unknown"
            
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("Nuclei version check timed out")
        except Exception as e:
            raise ToolExecutionError(f"Failed to get Nuclei version: {e}")
