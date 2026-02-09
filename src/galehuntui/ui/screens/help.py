from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    Markdown,
    TabbedContent,
    TabPane,
)
from textual.containers import Container
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
                    with TabbedContent(initial="global-shortcuts"):
                        with TabPane("Global", id="global-shortcuts"):
                            yield DataTable(id="shortcuts-global", cursor_type="row", zebra_stripes=True)

                        with TabPane("Per Screen", id="screen-shortcuts"):
                            yield DataTable(id="shortcuts-screens", cursor_type="row", zebra_stripes=True)
                
                with TabPane("Documentation", id="docs"):
                    yield Markdown(HELP_MD)
                
                with TabPane("About", id="about"):
                    yield Markdown(ABOUT_MD)
        yield Footer()

    def on_mount(self) -> None:
        """Initialize shortcuts table from live screen bindings."""
        all_rows = self._collect_shortcuts()
        global_rows = [row for row in all_rows if row[1] == "Global"]
        screen_rows = [row for row in all_rows if row[1] != "Global"]

        global_table = self.query_one("#shortcuts-global", DataTable)
        global_table.add_columns("Key", "Action")
        global_table.add_rows([(key, action) for key, _, action in global_rows])

        screens_table = self.query_one("#shortcuts-screens", DataTable)
        screens_table.add_columns("Screen", "Key", "Action")
        screens_table.add_rows(self._group_screen_rows(screen_rows))

        global_table.focus()

    def _collect_shortcuts(self) -> list[tuple[str, str, str]]:
        """Collect global and screen-level shortcuts from binding declarations."""
        rows: list[tuple[str, str, str]] = []

        rows.extend(self._extract_bindings(getattr(self.app, "BINDINGS", []), "Global"))

        screens = getattr(self.app, "SCREENS", {})
        for screen_name, screen_cls in screens.items():
            bindings = getattr(screen_cls, "BINDINGS", [])
            context = screen_name.replace("_", " ").title()
            rows.extend(self._extract_bindings(bindings, context))

        deduped = sorted(
            {(key, context, action) for key, context, action in rows},
            key=lambda item: (0 if item[1] == "Global" else 1, item[1], item[0], item[2]),
        )
        return list(deduped)

    def _extract_bindings(self, bindings: list[Any], context: str) -> list[tuple[str, str, str]]:
        """Normalize Textual binding declarations into table rows."""
        rows: list[tuple[str, str, str]] = []

        for binding in bindings:
            parsed = self._parse_binding(binding)
            if parsed is None:
                continue

            key, action, description = parsed
            action_label = description if description else action.replace("_", " ").title()
            rows.append((self._format_key_label(key), context, action_label))

        return rows

    def _group_screen_rows(self, rows: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        """Add visual grouping rows for per-screen shortcuts."""
        grouped: list[tuple[str, str, str]] = []
        current_context = ""

        for key, context, action in rows:
            if context != current_context:
                grouped.append((context, "", ""))
                current_context = context

            grouped.append(("", key, action))

        return grouped

    def _parse_binding(self, binding: Any) -> tuple[str, str, str] | None:
        """Parse tuple-style and Binding object declarations."""
        if isinstance(binding, Binding):
            return (
                str(binding.key),
                str(binding.action),
                str(binding.description or ""),
            )

        if isinstance(binding, tuple) and len(binding) >= 2:
            key = str(binding[0])
            action = str(binding[1])
            description = str(binding[2]) if len(binding) >= 3 else ""
            return (key, action, description)

        return None

    def _format_key_label(self, key: str) -> str:
        """Format raw Textual key notation for human-readable help table."""
        aliases = {
            "escape": "Esc",
            "enter": "Enter",
            "question_mark": "?",
            "space": "Space",
            "tab": "Tab",
        }
        normalized = key.lower()
        if normalized in aliases:
            return aliases[normalized]

        parts = normalized.split("+")
        pretty_parts: list[str] = []
        for part in parts:
            if len(part) == 1:
                pretty_parts.append(part.upper())
            else:
                pretty_parts.append(part.replace("_", " ").title())

        return "+".join(pretty_parts)
