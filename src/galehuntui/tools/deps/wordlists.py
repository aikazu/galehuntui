"""Wordlist management utilities."""

from pathlib import Path
from typing import Optional

from galehuntui.tools.deps.manager import DependencyManager


class WordlistManager:
    
    DEFAULT_WORDLISTS = {
        "directories": "seclists/Discovery/Web-Content/directory-list-2.3-medium.txt",
        "directories-small": "seclists/Discovery/Web-Content/directory-list-2.3-small.txt",
        "subdomains": "seclists/Discovery/DNS/subdomains-top1million-5000.txt",
        "subdomains-large": "seclists/Discovery/DNS/subdomains-top1million-110000.txt",
        "parameters": "seclists/Discovery/Web-Content/burp-parameter-names.txt",
        "passwords": "seclists/Passwords/Common-Credentials/10k-most-common.txt",
        "passwords-large": "seclists/Passwords/Common-Credentials/100k-most-common.txt",
        "usernames": "seclists/Usernames/top-usernames-shortlist.txt",
        "sqli": "fuzzdb/attack/sql-injection/detect/xplatform.txt",
        "xss": "fuzzdb/attack/xss/xss-rsnake.txt",
        "lfi": "seclists/Fuzzing/LFI/LFI-Jhaddix.txt",
    }
    
    def __init__(self, deps_manager: DependencyManager):
        self.deps_manager = deps_manager
        self.wordlists_dir = deps_manager.wordlists_dir
    
    def get_wordlist(self, name: str) -> Optional[Path]:
        if name in self.DEFAULT_WORDLISTS:
            path = self.wordlists_dir / self.DEFAULT_WORDLISTS[name]
        else:
            path = self.wordlists_dir / name
        
        return path if path.exists() else None
    
    def get_wordlist_or_raise(self, name: str) -> Path:
        path = self.get_wordlist(name)
        if path is None:
            raise FileNotFoundError(f"Wordlist not found: {name}")
        return path
    
    def list_available(self) -> list[Path]:
        if not self.wordlists_dir.exists():
            return []
        return sorted(self.wordlists_dir.rglob("*.txt"))
    
    def list_shortcuts(self) -> dict[str, Path | None]:
        return {
            name: self.get_wordlist(name)
            for name in self.DEFAULT_WORDLISTS
        }
    
    def search(self, pattern: str) -> list[Path]:
        if not self.wordlists_dir.exists():
            return []
        return sorted(self.wordlists_dir.rglob(f"*{pattern}*"))
