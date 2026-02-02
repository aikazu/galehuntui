from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    Markdown,
    TabbedContent,
    TabPane,
    Label,
    Button
)
from textual.containers import Container, Vertical
from textual.binding import Binding

HELP_MD = """
# GaleHunTUI Help

Welcome to **GaleHunTUI**, the terminal-based automated web pentesting application.

## Overview

GaleHunTUI orchestrates automated web pentesting workflows through an intuitive interface.
It supports:
- **Reconnaissance**: Subdomain enumeration, DNS resolution, HTTP probing.
- **Vulnerability Scanning**: Nuclei, XSS testing, SQLi testing.
- **Reporting**: Comprehensive reports in HTML and JSON.

## Workflow

1. **New Run**: Configure a target domain and select a profile (Quick, Standard, Deep).
2. **Monitor**: Watch the run progress in the Run Detail screen.
3. **Analyze**: Review findings in the Findings view.
4. **Export**: Generate reports for your stakeholders.

## Terminology

- **Profile**: A preset configuration of tools and scan depth.
- **Scope**: Rules defining what is allowed to be scanned (Allowlist/Denylist).
- **Mode**: Engagement type (Bug Bounty, Authorized, Aggressive) defining rate limits.

For more details, visit the documentation.
"""

ABOUT_MD = """
# About GaleHunTUI

**Version**: 0.1.0-alpha
**License**: MIT

## Team
Developed by the GaleHunTUI Open Source Community.

## Credits
Powered by amazing open-source tools:
- subfinder, dnsx, httpx, nuclei (ProjectDiscovery)
- dalfox (hahwul)
- ffuf (ffuf)
- sqlmap (sqlmapproject)
- textual (Textualize)
"""

class HelpScreen(Screen):
    """Screen for displaying help and documentation."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(classes="help-container"):
            with TabbedContent(initial="shortcuts"):
                with TabPane("Keyboard Shortcuts", id="shortcuts"):
                    yield DataTable(cursor_type="row", zebra_stripes=True)
                
                with TabPane("Documentation", id="docs"):
                    yield Markdown(HELP_MD)
                
                with TabPane("About", id="about"):
                    yield Markdown(ABOUT_MD)
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the data table."""
        table = self.query_one(DataTable)
        table.add_columns("Key", "Context", "Action")
        
        shortcuts = [
            ("?", "Global", "Show Help (this screen)"),
            ("Esc", "Global", "Back / Cancel"),
            ("Ctrl+Q", "Global", "Quit Application"),
            ("Ctrl+S", "Global", "Save Settings / Configuration"),
            ("Ctrl+T", "Global", "Open Tools Manager"),
            ("Ctrl+N", "Global", "Start New Run"),
            ("Tab", "Forms", "Next Field"),
            ("/", "Lists", "Search / Filter"),
            ("j / k", "Navigation", "Move Up / Down"),
            ("g / G", "Navigation", "Go to Top / Bottom"),
            ("Enter", "Controls", "Select / Activate"),
        ]
        
        table.add_rows(shortcuts)
        table.focus()
