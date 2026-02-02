"""Base classes and interfaces for tool adapters.

This module defines the abstract ToolAdapter interface that all tool adapters
must implement. It ensures consistent behavior across all tools and provides
a standard contract for tool execution, output parsing, and management.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Optional

from galehuntui.core.models import Finding, ToolConfig, ToolResult


class ToolAdapter(ABC):
    """Abstract base class for all tool adapters.
    
    All tool adapters must implement this interface to ensure consistent
    behavior and integration with the pipeline orchestrator.
    
    Attributes:
        name: Tool identifier (e.g., "httpx", "nuclei")
        required: Whether tool is required for basic operation
        mode_required: Minimum engagement mode required (None if available in all modes)
    """
    
    name: str
    required: bool
    mode_required: Optional[str]
    
    @abstractmethod
    async def run(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> ToolResult:
        """Execute tool with given inputs and configuration.
        
        This method runs the tool to completion and returns the full result.
        For real-time output streaming, use the `stream()` method instead.
        
        Args:
            inputs: Input data for the tool (URLs, domains, files, etc.)
            config: Tool execution configuration
            
        Returns:
            ToolResult containing stdout, stderr, exit code, duration, and output path
            
        Raises:
            ToolNotFoundError: If tool binary is not found
            ToolTimeoutError: If tool execution exceeds timeout
            ToolExecutionError: If tool execution fails
        """
        pass
    
    @abstractmethod
    async def stream(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> AsyncIterator[str]:
        """Stream tool output in real-time.
        
        This method yields output lines as they are produced by the tool,
        allowing for real-time display in the TUI or CLI.
        
        Args:
            inputs: Input data for the tool (URLs, domains, files, etc.)
            config: Tool execution configuration
            
        Yields:
            Output lines from the tool as they are produced
            
        Raises:
            ToolNotFoundError: If tool binary is not found
            ToolTimeoutError: If tool execution exceeds timeout
            ToolExecutionError: If tool execution fails
        """
        pass
    
    @abstractmethod
    def parse_output(self, raw: str) -> list[Finding]:
        """Parse tool output to normalized findings.
        
        Converts tool-specific output format to normalized Finding objects.
        Must handle both JSON and text output formats as needed.
        
        Args:
            raw: Raw output from the tool (stdout)
            
        Returns:
            List of normalized Finding objects
            
        Note:
            Empty list is returned if no findings are detected.
            Malformed output should be logged but not raise exceptions.
        """
        pass
    
    @abstractmethod
    def build_command(
        self,
        inputs: list[str],
        config: ToolConfig,
    ) -> list[str]:
        """Build command line arguments for tool execution.
        
        Constructs the complete command including the tool binary path,
        all flags, arguments, and input handling.
        
        Args:
            inputs: Input data for the tool
            config: Tool execution configuration
            
        Returns:
            List of command arguments ready for subprocess execution
            
        Example:
            >>> adapter.build_command(
            ...     inputs=["https://example.com"],
            ...     config=ToolConfig(name="httpx", timeout=30)
            ... )
            ["/tools/bin/httpx", "-json", "-silent", "-timeout", "30"]
        """
        pass
    
    @abstractmethod
    async def check_available(self) -> bool:
        """Check if tool is installed and accessible.
        
        Verifies that the tool binary exists, is executable, and can be run.
        This should be a fast check suitable for startup validation.
        
        Returns:
            True if tool is available, False otherwise
            
        Note:
            This method should not raise exceptions. Return False for any errors.
        """
        pass
    
    @abstractmethod
    def get_version(self) -> str:
        """Return installed tool version.
        
        Executes the tool with version flag and parses the output.
        Used for tool verification and audit logging.
        
        Returns:
            Version string (e.g., "v2.0.0", "1.5.3")
            
        Raises:
            ToolNotFoundError: If tool is not installed
            ToolExecutionError: If version check fails
            
        Note:
            Version format should be normalized to semantic versioning where possible.
        """
        pass


class ToolAdapterBase(ToolAdapter):
    """Base implementation with common utilities for tool adapters.
    
    Provides helper methods for common operations like path handling,
    input file creation, and output parsing. Concrete adapters should
    inherit from this class instead of ToolAdapter directly.
    
    Args:
        bin_path: Path to the directory containing tool binaries
    """
    
    def __init__(self, bin_path: Path):
        """Initialize tool adapter with binary path.
        
        Args:
            bin_path: Path to directory containing tool binaries
        """
        self.bin_path = bin_path
        self._tool_binary = bin_path / self.name
    
    def _get_tool_path(self) -> Path:
        """Get path to tool binary.
        
        Returns:
            Absolute path to tool binary
        """
        return self._tool_binary
    
    async def check_available(self) -> bool:
        """Check if tool is installed and accessible.
        
        Default implementation checks if binary exists and is executable.
        
        Returns:
            True if tool is available, False otherwise
        """
        tool_path = self._get_tool_path()
        if not tool_path.exists():
            return False
        if not tool_path.is_file():
            return False
        # Check if executable (on Unix systems)
        try:
            return tool_path.stat().st_mode & 0o111 != 0
        except (OSError, PermissionError):
            return False
    
    def _create_input_file(self, inputs: list[str], output_dir: Path) -> Path:
        """Create temporary input file from inputs list.
        
        Helper method to write inputs to a file for tools that accept
        input via file rather than stdin or arguments.
        
        Args:
            inputs: List of input strings (URLs, domains, etc.)
            output_dir: Directory to write input file
            
        Returns:
            Path to created input file
        """
        input_file = output_dir / f"{self.name}_input.txt"
        input_file.write_text("\n".join(inputs))
        return input_file
    
    def _parse_json_lines(self, raw: str) -> list[dict]:
        """Parse JSON Lines format output.
        
        Helper method for parsing JSONL output common in many tools.
        
        Args:
            raw: Raw output in JSON Lines format
            
        Returns:
            List of parsed JSON objects
        """
        import json
        
        results = []
        for line in raw.strip().split("\n"):
            if not line:
                continue
            try:
                results.append(json.loads(line))
            except json.JSONDecodeError:
                # Skip malformed lines
                continue
        return results
