"""Hydra tool adapter for authentication brute forcing.

Hydra is a parallelized login cracker which supports numerous protocols.
It's very fast and flexible, supporting many attack modes.
"""

import asyncio
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


class HydraAdapter(ToolAdapterBase):
    """Adapter for Hydra authentication brute force tool.
    
    Hydra performs rapid dictionary attacks against network authentication services.
    Supports HTTP, FTP, SSH, and many other protocols.
    
    Attributes:
        name: Tool identifier ("hydra")
        required: False - Optional for authentication testing
        mode_required: "AUTHORIZED" - Requires authorized engagement mode
    """
    
    name = "hydra"
    required = False
    mode_required = "AUTHORIZED"
    
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> list[str]:
        """Build Hydra command line arguments.
        
        Args:
            inputs: List of targets (format: service://target:port)
            config: Tool execution configuration
            
        Returns:
            Complete command arguments for Hydra execution
        """
        cmd = [
            str(self._get_tool_path()),
            "-V",  # Verbose output
        ]
        
        # Add timeout if specified (Hydra uses -w for timeout per connection)
        if config.timeout:
            # Timeout per connection attempt
            timeout_per_attempt = min(config.timeout, 30)
            cmd.extend(["-w", str(timeout_per_attempt)])
        
        # Add parallel tasks (mapping from rate_limit)
        if config.rate_limit:
            tasks = min(config.rate_limit, 64)  # Hydra default max is 64
            cmd.extend(["-t", str(tasks)])
        
        # Add any custom arguments from config (like -L, -P, -l, -p for user/pass lists)
        if config.args:
            cmd.extend(config.args)
        
        # Add target(s) - Hydra expects target at the end
        if len(inputs) >= 1:
            input_path = Path(inputs[0])
            if input_path.exists() and input_path.is_file():
                # File with targets (using -M flag)
                cmd.extend(["-M", str(input_path)])
            else:
                # Single target - will be added at the end with service
                # Format: service://target:port or just target
                cmd.append(inputs[0])
        
        return cmd
    
    async def run(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> ToolResult:
        """Execute Hydra with given inputs and configuration.
        
        Args:
            inputs: Targets to test (service://host:port format)
            config: Tool execution configuration
            
        Returns:
            ToolResult containing execution results and output path
            
        Raises:
            ToolNotFoundError: If Hydra is not found
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
            raise ToolNotFoundError(f"Hydra not found at {tool_path}")
        
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
                    f"Hydra execution exceeded timeout of {config.timeout}s"
                )
            
            duration = time.time() - start_time
            
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")
            exit_code = process.returncode or 0
            
            # Save output to file
            output_path = Path(f"/tmp/hydra_output_{uuid4().hex[:8]}.txt")
            output_path.write_text(stdout)
            
            return ToolResult(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                duration=duration,
                output_path=output_path,
            )
            
        except FileNotFoundError:
            raise ToolNotFoundError(f"Hydra binary not found: {cmd[0]}")
        except Exception as e:
            if isinstance(e, ToolTimeoutError):
                raise
            raise ToolExecutionError(f"Hydra execution failed: {e}")
    
    async def stream(  # type: ignore[override]
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> AsyncIterator[str]:
        """Stream Hydra output in real-time.
        
        Args:
            inputs: Targets to test
            config: Tool execution configuration
            
        Yields:
            Output lines from Hydra as they are produced
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not await self.check_available():
            raise ToolNotFoundError(f"Hydra not found at {tool_path}")
        
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
            raise ToolNotFoundError(f"Hydra binary not found: {cmd[0]}")
        except Exception as e:
            raise ToolExecutionError(f"Hydra streaming failed: {e}")
    
    def parse_output(self, raw: str) -> list[Finding]:
        """Parse Hydra text output to normalized findings.
        
        Hydra outputs successful authentications in specific format:
        [PORT][PROTOCOL] host: HOST   login: USER   password: PASS
        
        Args:
            raw: Raw text output from Hydra
            
        Returns:
            List of normalized Finding objects
        """
        findings = []
        lines = raw.split("\n")
        
        for line in lines:
            line = line.strip()
            
            # Look for successful login attempts
            # Format: [80][http-post-form] host: 10.0.0.1   login: admin   password: admin123
            if "login:" in line and "password:" in line:
                finding = self._create_finding_from_success(line)
                if finding:
                    findings.append(finding)
        
        return findings
    
    def _create_finding_from_success(self, line: str) -> Optional[Finding]:
        """Create Finding object from successful authentication.
        
        Args:
            line: Success line from Hydra output
            
        Returns:
            Finding object or None
        """
        try:
            # Parse the line to extract components
            # Format: [PORT][PROTOCOL] host: HOST   login: USER   password: PASS
            
            # Extract service/protocol
            service = "unknown"
            if "[" in line and "]" in line:
                parts = line.split("]")
                if len(parts) >= 2:
                    service = parts[1].replace("[", "").strip()
            
            # Extract host
            host = ""
            if "host:" in line:
                host_part = line.split("host:")[1].split("login:")[0].strip()
                host = host_part
            
            # Extract login
            login = ""
            if "login:" in line:
                login_part = line.split("login:")[1].split("password:")[0].strip()
                login = login_part
            
            # Extract password
            password = ""
            if "password:" in line:
                password_part = line.split("password:")[1].strip()
                password = password_part
            
            if not host or not login:
                return None
            
            url = f"{service}://{host}"
            
            title = f"Weak credentials found via {self.name}"
            description = f"Weak or default credentials discovered on {service} service at {host}. Username: {login}"
            
            # Don't include password in description for security
            # It will be in evidence files
            
            finding = Finding(
                id=str(uuid4()),
                run_id="",
                type="weak-credentials",
                severity=Severity.HIGH,
                confidence=Confidence.CONFIRMED,
                host=host,
                url=url,
                parameter=None,
                evidence_paths=[],  # Should be populated with credential file
                tool=self.name,
                timestamp=datetime.now(),
                title=title,
                description=description,
                reproduction_steps=[
                    f"Service: {service}",
                    f"Host: {host}",
                    f"Username: {login}",
                    "Password: [Stored in evidence]",
                    "Attempt authentication with these credentials",
                ],
                remediation="Enforce strong password policies. Disable or change default credentials. Implement account lockout policies after failed login attempts. Use multi-factor authentication where possible.",
                references=[
                    "https://owasp.org/www-project-top-ten/2017/A2_2017-Broken_Authentication",
                    "https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html",
                ],
            )
            
            return finding
            
        except Exception:
            # Failed to parse line
            return None
    
    def get_version(self) -> str:
        """Get Hydra version.
        
        Returns:
            Version string
        """
        from galehuntui.core.exceptions import (
            ToolNotFoundError,
            ToolExecutionError,
        )
        
        tool_path = self._get_tool_path()
        if not tool_path.exists():
            raise ToolNotFoundError(f"Hydra not found at {tool_path}")
        
        try:
            result = subprocess.run(
                [str(tool_path), "-h"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            # Hydra version is in the help output, first line usually
            # Format: "Hydra v9.5 (c) 2023..."
            output = result.stdout.strip()
            lines = output.split("\n")
            if lines:
                first_line = lines[0]
                if "hydra" in first_line.lower() and "v" in first_line.lower():
                    # Extract version
                    parts = first_line.split()
                    for part in parts:
                        if part.startswith("v") or part.startswith("V"):
                            return part
            
            return "unknown"
            
        except subprocess.TimeoutExpired:
            raise ToolExecutionError("Hydra version check timed out")
        except Exception as e:
            raise ToolExecutionError(f"Failed to get Hydra version: {e}")
