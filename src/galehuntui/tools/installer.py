"""Tool installation and management."""

import asyncio
import hashlib
import platform
import shutil
import tarfile
import zipfile
from pathlib import Path
from typing import Any, Optional

import httpx
import yaml

from galehuntui.core.exceptions import ToolInstallError


class ToolInstaller:
    """Manages tool installation, updates, and verification."""

    def __init__(self, tools_dir: Path):
        """Initialize installer.
        
        Args:
            tools_dir: Base directory for tools (e.g., tools/)
        """
        self.tools_dir = tools_dir
        self.bin_dir = tools_dir / "bin"
        self.scripts_dir = tools_dir / "scripts"
        self.registry_path = tools_dir / "registry.yaml"
        self.versions_path = tools_dir / "versions.json"
        self.checksums_path = tools_dir / "checksums.json"
        
        self.bin_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def get_platform() -> str:
        """Detect current platform.
        
        Returns:
            Platform identifier (linux, darwin, windows)
        """
        system = platform.system().lower()
        if system == "darwin":
            return "darwin"
        if system == "windows":
            return "windows"
        return "linux"
    
    @staticmethod
    def get_arch() -> str:
        """Detect system architecture.
        
        Returns:
            Architecture identifier (amd64, arm64, 386)
        """
        machine = platform.machine().lower()
        if machine in ("x86_64", "amd64"):
            return "amd64"
        if machine in ("aarch64", "arm64"):
            return "arm64"
        if machine in ("i386", "i686"):
            return "386"
        return machine
    
    def load_registry(self) -> dict[str, Any]:
        """Load tool registry from YAML.
        
        Returns:
            Registry data dictionary
            
        Raises:
            ToolInstallError: If registry cannot be loaded
        """
        if not self.registry_path.exists():
            raise ToolInstallError(f"Registry not found: {self.registry_path}")
        
        try:
            content = self.registry_path.read_text()
            return yaml.safe_load(content)
        except Exception as e:
            raise ToolInstallError(f"Failed to load registry: {e}") from e
    
    async def get_latest_release(
        self,
        repo: str,
        *,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """Fetch latest release info from GitHub API.
        
        Args:
            repo: GitHub repository (e.g., "projectdiscovery/subfinder")
            timeout: Request timeout in seconds
            
        Returns:
            Release data dictionary with 'tag_name' and 'assets'
            
        Raises:
            ToolInstallError: If API request fails
        """
        url = f"https://api.github.com/repos/{repo}/releases/latest"
        
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    url,
                    headers={"Accept": "application/vnd.github+json"},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            raise ToolInstallError(
                f"GitHub API error for {repo}: {e.response.status_code}"
            ) from e
        except Exception as e:
            raise ToolInstallError(
                f"Failed to fetch release info for {repo}: {e}"
            ) from e
    
    def find_asset(
        self,
        assets: list[dict[str, Any]],
        platform_str: str,
        arch: str,
        patterns: list[str],
    ) -> Optional[dict[str, Any]]:
        """Find matching asset from release assets.
        
        Args:
            assets: List of asset dictionaries from GitHub API
            platform_str: Target platform (linux, darwin, windows)
            arch: Target architecture (amd64, arm64, etc.)
            patterns: Additional patterns to match
            
        Returns:
            Matching asset dict or None
        """
        search_terms = [platform_str, arch] + patterns
        
        for asset in assets:
            name = asset["name"].lower()
            
            if all(term.lower() in name for term in search_terms):
                if any(ext in name for ext in [".sha256", ".md5", ".sig", ".asc"]):
                    continue
                return asset
        
        return None
    
    async def download_file(
        self,
        url: str,
        dest: Path,
        *,
        timeout: int = 300,
    ) -> Path:
        """Download file from URL.
        
        Args:
            url: Download URL
            dest: Destination file path
            timeout: Download timeout in seconds
            
        Returns:
            Path to downloaded file
            
        Raises:
            ToolInstallError: If download fails
        """
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    
                    with dest.open("wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
            
            return dest
        except Exception as e:
            if dest.exists():
                dest.unlink()
            raise ToolInstallError(f"Download failed: {e}") from e
    
    def verify_checksum(
        self,
        file_path: Path,
        expected: str,
        algorithm: str = "sha256",
    ) -> bool:
        """Verify file checksum.
        
        Args:
            file_path: Path to file
            expected: Expected checksum (hex string)
            algorithm: Hash algorithm (sha256, md5)
            
        Returns:
            True if checksum matches
        """
        if algorithm == "sha256":
            hasher = hashlib.sha256()
        elif algorithm == "md5":
            hasher = hashlib.md5()
        else:
            return False
        
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        
        return hasher.hexdigest().lower() == expected.lower()
    
    def extract_archive(self, archive_path: Path, dest_dir: Path) -> Path:
        """Extract archive (zip or tar.gz).
        
        Args:
            archive_path: Path to archive file
            dest_dir: Destination directory
            
        Returns:
            Path to destination directory
            
        Raises:
            ToolInstallError: If extraction fails
        """
        try:
            if archive_path.suffix == ".zip" or archive_path.name.endswith(".zip"):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    zf.extractall(dest_dir)
            elif archive_path.name.endswith(".tar.gz") or archive_path.name.endswith(".tgz"):
                with tarfile.open(archive_path, "r:gz") as tf:
                    tf.extractall(dest_dir)
            elif archive_path.name.endswith(".tar"):
                with tarfile.open(archive_path, "r") as tf:
                    tf.extractall(dest_dir)
            else:
                raise ToolInstallError(f"Unsupported archive format: {archive_path.suffix}")
            
            return dest_dir
        except Exception as e:
            raise ToolInstallError(f"Archive extraction failed: {e}") from e
    
    async def install_from_github_release(
        self,
        tool_name: str,
        repo: str,
        binary_name: str,
        *,
        asset_patterns: Optional[list[str]] = None,
        checksum: Optional[str] = None,
    ) -> Path:
        """Install tool from GitHub release.
        
        Args:
            tool_name: Tool identifier
            repo: GitHub repository (owner/repo)
            binary_name: Name of the binary to install
            asset_patterns: Additional patterns to match asset
            checksum: Expected SHA256 checksum (if known)
            
        Returns:
            Path to installed binary
            
        Raises:
            ToolInstallError: If installation fails
        """
        platform_str = self.get_platform()
        arch = self.get_arch()
        
        release = await self.get_latest_release(repo)
        version = release["tag_name"]
        
        patterns = asset_patterns or []
        asset = self.find_asset(release["assets"], platform_str, arch, patterns)
        
        if asset is None:
            raise ToolInstallError(
                f"No matching asset found for {tool_name} "
                f"(platform={platform_str}, arch={arch})"
            )
        
        download_url = asset["browser_download_url"]
        temp_dir = self.tools_dir / "tmp"
        temp_dir.mkdir(exist_ok=True)
        
        archive_path = temp_dir / asset["name"]
        await self.download_file(download_url, archive_path)
        
        if checksum:
            if not self.verify_checksum(archive_path, checksum):
                archive_path.unlink()
                raise ToolInstallError(f"Checksum verification failed for {tool_name}")
        
        binary_path = self.bin_dir / binary_name
        
        if archive_path.name.endswith((".zip", ".tar.gz", ".tgz", ".tar")):
            extract_dir = temp_dir / f"{tool_name}_extract"
            extract_dir.mkdir(exist_ok=True)
            self.extract_archive(archive_path, extract_dir)
            
            found_binary = None
            for candidate in extract_dir.rglob("*"):
                if candidate.is_file() and candidate.name == binary_name:
                    found_binary = candidate
                    break
            
            if found_binary is None:
                raise ToolInstallError(
                    f"Binary '{binary_name}' not found in extracted archive"
                )
            
            shutil.move(str(found_binary), str(binary_path))
            shutil.rmtree(extract_dir)
        else:
            shutil.move(str(archive_path), str(binary_path))
        
        binary_path.chmod(0o755)
        
        if archive_path.exists():
            archive_path.unlink()
        
        return binary_path
    
    async def install_from_git(
        self,
        tool_name: str,
        repo_url: str,
        *,
        branch: str = "master",
    ) -> Path:
        """Install tool by cloning git repository.
        
        Args:
            tool_name: Tool identifier
            repo_url: Git repository URL
            branch: Branch to clone
            
        Returns:
            Path to cloned repository
            
        Raises:
            ToolInstallError: If git clone fails
        """
        dest_path = self.scripts_dir / tool_name
        
        if dest_path.exists():
            shutil.rmtree(dest_path)
        
        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                "--depth=1",
                "--branch",
                branch,
                repo_url,
                str(dest_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise ToolInstallError(
                    f"Git clone failed: {stderr.decode()}"
                )
            
            return dest_path
        except FileNotFoundError:
            raise ToolInstallError("git command not found - please install git") from None
        except Exception as e:
            raise ToolInstallError(f"Git clone failed: {e}") from e
    
    async def install_tool(self, tool_name: str) -> Path:
        """Install a tool from registry.
        
        Args:
            tool_name: Tool identifier from registry
            
        Returns:
            Path to installed tool
            
        Raises:
            ToolInstallError: If installation fails
        """
        registry = self.load_registry()
        
        if tool_name not in registry["tools"]:
            raise ToolInstallError(f"Tool '{tool_name}' not found in registry")
        
        tool_config = registry["tools"][tool_name]
        install_method = tool_config["install_method"]
        
        if install_method == "github_release":
            return await self.install_from_github_release(
                tool_name=tool_name,
                repo=tool_config["repo"],
                binary_name=tool_config.get("binary_name", tool_name),
                asset_patterns=tool_config.get("asset_patterns", []),
                checksum=tool_config.get("checksum"),
            )
        elif install_method == "git":
            return await self.install_from_git(
                tool_name=tool_name,
                repo_url=tool_config["repo_url"],
                branch=tool_config.get("branch", "master"),
            )
        else:
            raise ToolInstallError(
                f"Unsupported install method: {install_method}"
            )
    
    async def install_all(self, *, skip_errors: bool = False) -> dict[str, Path | Exception]:
        """Install all tools from registry.
        
        Args:
            skip_errors: Continue on individual tool failures
            
        Returns:
            Dict mapping tool names to installed paths or exceptions
        """
        registry = self.load_registry()
        results: dict[str, Path | Exception] = {}
        
        for tool_name in registry["tools"]:
            try:
                path = await self.install_tool(tool_name)
                results[tool_name] = path
            except Exception as e:
                if skip_errors:
                    results[tool_name] = e
                else:
                    raise
        
        return results
    
    def verify_tool(self, tool_name: str) -> bool:
        """Verify tool is installed and executable.
        
        Args:
            tool_name: Tool identifier
            
        Returns:
            True if tool is available
        """
        binary_path = self.bin_dir / tool_name
        script_path = self.scripts_dir / tool_name
        
        if binary_path.exists() and binary_path.is_file():
            return True
        
        if script_path.exists() and script_path.is_dir():
            return True
        
        return False
    
    async def get_tool_version(self, tool_name: str) -> Optional[str]:
        """Get installed tool version.
        
        Args:
            tool_name: Tool identifier
            
        Returns:
            Version string or None if cannot be determined
        """
        binary_path = self.bin_dir / tool_name
        
        if not binary_path.exists():
            return None
        
        try:
            for flag in ["-version", "--version", "-v"]:
                process = await asyncio.create_subprocess_exec(
                    str(binary_path),
                    flag,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=5.0,
                )
                
                output = (stdout + stderr).decode().strip()
                if output:
                    return output.split("\n")[0]
        except Exception:
            pass
        
        return None
