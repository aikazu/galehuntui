"""Tool adapters for external security tools.

This package contains adapters for integrating external pentesting tools
into the GaleHunTUI pipeline. Each adapter implements the ToolAdapter interface.
"""

from galehuntui.tools.adapters.nuclei import NucleiAdapter
from galehuntui.tools.adapters.subfinder import SubfinderAdapter

__all__ = [
    "NucleiAdapter",
    "SubfinderAdapter",
]
