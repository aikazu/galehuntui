"""Dependency management for wordlists and templates."""

import asyncio
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml

from galehuntui.core.exceptions import DependencyError


class DependencyType(str, Enum):
    TEMPLATES = "templates"
    WORDLISTS = "wordlists"


class DependencyStatus(str, Enum):
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    UPDATE_AVAILABLE = "update_available"
    INSTALLING = "installing"
    ERROR = "error"


@dataclass
class DependencyInfo:
    id: str
    name: str
    type: DependencyType
    description: str
    status: DependencyStatus
    installed_path: Optional[Path] = None
    version: Optional[str] = None
    size_estimate: Optional[str] = None
    required: bool = False


class DependencyManager:
    
    def __init__(self, deps_dir: Path, registry_path: Optional[Path] = None):
        self.deps_dir = deps_dir
        self.templates_dir = deps_dir / "templates"
        self.wordlists_dir = deps_dir / "wordlists"
        self.registry_path = registry_path or (
            Path(__file__).parent / "registry.yaml"
        )
        self._registry: dict | None = None
    
    def _load_registry(self) -> dict:
        if self._registry is None:
            if not self.registry_path.exists():
                raise DependencyError(f"Registry not found: {self.registry_path}")
            content = self.registry_path.read_text()
            self._registry = yaml.safe_load(content) or {}
        return self._registry
    
    async def get_dependencies(self) -> list[DependencyInfo]:
        registry = self._load_registry()
        deps = []
        
        for dep_id, config in registry.get("dependencies", {}).items():
            status = await self._check_status(dep_id, config)
            install_path = self._get_install_path(dep_id, config)
            
            deps.append(DependencyInfo(
                id=dep_id,
                name=config["name"],
                type=DependencyType(config["type"]),
                description=config.get("description", ""),
                status=status,
                installed_path=install_path if install_path.exists() else None,
                size_estimate=config.get("size_estimate"),
                required=config.get("required", False),
            ))
        
        return deps
    
    def _get_install_path(self, dep_id: str, config: dict) -> Path:
        dep_type = DependencyType(config["type"])
        base_dir = self.templates_dir if dep_type == DependencyType.TEMPLATES else self.wordlists_dir
        return base_dir / dep_id
    
    async def _check_status(self, dep_id: str, config: dict) -> DependencyStatus:
        install_path = self._get_install_path(dep_id, config)
        
        if not install_path.exists():
            return DependencyStatus.NOT_INSTALLED
        
        return DependencyStatus.INSTALLED
    
    async def install(self, dep_id: str) -> bool:
        registry = self._load_registry()
        config = registry.get("dependencies", {}).get(dep_id)
        
        if config is None:
            raise DependencyError(f"Unknown dependency: {dep_id}")
        
        dep_type = DependencyType(config["type"])
        base_dir = self.templates_dir if dep_type == DependencyType.TEMPLATES else self.wordlists_dir
        base_dir.mkdir(parents=True, exist_ok=True)
        install_path = base_dir / dep_id
        
        if config["source"] == "git":
            return await self._git_clone(
                config["url"],
                install_path,
                branch=config.get("branch", "master"),
            )
        
        raise DependencyError(f"Unsupported source type: {config['source']}")
    
    async def update(self, dep_id: str) -> bool:
        registry = self._load_registry()
        config = registry.get("dependencies", {}).get(dep_id)
        
        if config is None:
            raise DependencyError(f"Unknown dependency: {dep_id}")
        
        install_path = self._get_install_path(dep_id, config)
        
        if not install_path.exists():
            return await self.install(dep_id)
        
        if config["source"] == "git":
            return await self._git_pull(install_path)
        
        return False
    
    async def update_all(self, *, skip_errors: bool = False) -> dict[str, bool | Exception]:
        results: dict[str, bool | Exception] = {}
        deps = await self.get_dependencies()
        
        for dep in deps:
            if dep.status == DependencyStatus.NOT_INSTALLED:
                continue
            try:
                results[dep.id] = await self.update(dep.id)
            except Exception as e:
                if skip_errors:
                    results[dep.id] = e
                else:
                    raise
        
        return results
    
    async def install_all(self, *, skip_errors: bool = False) -> dict[str, bool | Exception]:
        results: dict[str, bool | Exception] = {}
        deps = await self.get_dependencies()
        
        for dep in deps:
            try:
                results[dep.id] = await self.install(dep.id)
            except Exception as e:
                if skip_errors:
                    results[dep.id] = e
                else:
                    raise
        
        return results
    
    async def verify(self, dep_id: str) -> bool:
        registry = self._load_registry()
        config = registry.get("dependencies", {}).get(dep_id)
        
        if config is None:
            return False
        
        install_path = self._get_install_path(dep_id, config)
        return install_path.exists() and install_path.is_dir()
    
    async def uninstall(self, dep_id: str) -> bool:
        registry = self._load_registry()
        config = registry.get("dependencies", {}).get(dep_id)
        
        if config is None:
            raise DependencyError(f"Unknown dependency: {dep_id}")
        
        install_path = self._get_install_path(dep_id, config)
        
        if not install_path.exists():
            return True
        
        import shutil
        shutil.rmtree(install_path)
        return True
    
    async def _git_clone(self, url: str, dest: Path, branch: str = "master") -> bool:
        if dest.exists():
            return True
        
        process = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth=1", "--branch", branch, url, str(dest),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise DependencyError(f"Git clone failed: {stderr.decode()}")
        
        return True
    
    async def _git_pull(self, repo_path: Path) -> bool:
        process = await asyncio.create_subprocess_exec(
            "git", "-C", str(repo_path), "pull", "--ff-only",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise DependencyError(f"Git pull failed: {stderr.decode()}")
        
        return True
