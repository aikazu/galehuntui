from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DataTable, Input, Select, Static

from galehuntui.core.models import Severity, Confidence


SEVERITY_COLORS = {
    Severity.CRITICAL: "red bold",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.LOW: "blue",
    Severity.INFO: "dim",
}

SEVERITY_ORDER = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}

CONFIDENCE_COLORS = {
    Confidence.CONFIRMED: "green",
    Confidence.FIRM: "cyan",
    Confidence.TENTATIVE: "yellow",
}


class SortColumn(str, Enum):
    SEVERITY = "severity"
    TYPE = "type"
    HOST = "host"
    TIMESTAMP = "timestamp"


class SortDirection(str, Enum):
    ASC = "asc"
    DESC = "desc"


@dataclass
class FindingRow:
    id: str
    severity: Severity
    finding_type: str
    host: str
    url: str
    confidence: Confidence
    timestamp: datetime
    title: str
    tool: str


class FindingsTableWidget(Widget):
    DEFAULT_CSS = """
    FindingsTableWidget {
        layout: vertical;
        height: 100%;
    }
    FindingsTableWidget .findings-toolbar {
        height: 3;
        background: #1a1c29;
        padding: 0 1;
    }
    FindingsTableWidget .findings-toolbar Select {
        width: 16;
        margin-right: 1;
    }
    FindingsTableWidget .findings-toolbar Input {
        width: 1fr;
    }
    FindingsTableWidget .findings-toolbar Static {
        width: auto;
        padding: 0 1;
        content-align: center middle;
    }
    FindingsTableWidget DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("s", "cycle_sort", "Sort"),
        Binding("f", "focus_filter", "Filter"),
        Binding("e", "export_findings", "Export"),
        Binding("enter", "select_finding", "View Details"),
    ]

    class FindingSelected(Message):
        def __init__(self, finding_id: str) -> None:
            self.finding_id = finding_id
            super().__init__()

    severity_filter: reactive[Optional[Severity]] = reactive(None)
    type_filter: reactive[str] = reactive("")
    sort_column: reactive[SortColumn] = reactive(SortColumn.SEVERITY)
    sort_direction: reactive[SortDirection] = reactive(SortDirection.ASC)

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._findings: list[FindingRow] = []
        self._visible_ids: list[str] = []

    def compose(self) -> ComposeResult:
        severity_options = [("All", "")] + [
            (sev.value.upper(), sev.value) for sev in Severity
        ]
        with Horizontal(classes="findings-toolbar"):
            yield Select(
                severity_options,
                value="",
                id="severity-filter",
                prompt="Severity",
            )
            yield Input(placeholder="Filter by type or host...", id="type-filter")
            yield Static("0 findings", id="findings-count")
        yield DataTable(id="findings-table", cursor_type="row")

    def on_mount(self) -> None:
        table = self.query_one("#findings-table", DataTable)
        table.add_columns("ID", "Severity", "Type", "Host", "Confidence", "Tool")
        table.cursor_type = "row"

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "severity-filter":
            if event.value == "":
                self.severity_filter = None
            else:
                self.severity_filter = Severity(event.value)
            self._refresh_table()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "type-filter":
            self.type_filter = event.value
            self._refresh_table()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key and event.row_key.value:
            self.post_message(self.FindingSelected(str(event.row_key.value)))

    def add_finding(self, finding: FindingRow) -> None:
        self._findings.append(finding)
        if self._should_display(finding):
            self._add_row(finding)
            self._update_count()

    def add_findings(self, findings: list[FindingRow]) -> None:
        for finding in findings:
            self._findings.append(finding)
        self._refresh_table()

    def clear(self) -> None:
        self._findings.clear()
        self._visible_ids.clear()
        table = self.query_one("#findings-table", DataTable)
        table.clear()
        self._update_count()

    def get_finding(self, finding_id: str) -> Optional[FindingRow]:
        for finding in self._findings:
            if finding.id == finding_id:
                return finding
        return None

    def get_selected_finding(self) -> Optional[FindingRow]:
        table = self.query_one("#findings-table", DataTable)
        if table.cursor_row is not None and self._visible_ids:
            idx = table.cursor_row
            if 0 <= idx < len(self._visible_ids):
                return self.get_finding(self._visible_ids[idx])
        return None

    def export_to_file(self, path: Path) -> int:
        visible = [f for f in self._findings if self._should_display(f)]
        data = []
        for f in visible:
            data.append({
                "id": f.id,
                "severity": f.severity.value,
                "type": f.finding_type,
                "host": f.host,
                "url": f.url,
                "confidence": f.confidence.value,
                "timestamp": f.timestamp.isoformat(),
                "title": f.title,
                "tool": f.tool,
            })
        with path.open("w") as fp:
            json.dump(data, fp, indent=2)
        return len(data)

    def _should_display(self, finding: FindingRow) -> bool:
        if self.severity_filter and finding.severity != self.severity_filter:
            return False
        if self.type_filter:
            query = self.type_filter.lower()
            if query not in finding.finding_type.lower() and query not in finding.host.lower():
                return False
        return True

    def _add_row(self, finding: FindingRow) -> None:
        table = self.query_one("#findings-table", DataTable)
        sev_color = SEVERITY_COLORS[finding.severity]
        conf_color = CONFIDENCE_COLORS[finding.confidence]

        table.add_row(
            finding.id,
            f"[{sev_color}]{finding.severity.value.upper()}[/]",
            finding.finding_type,
            finding.host,
            f"[{conf_color}]{finding.confidence.value}[/]",
            finding.tool,
            key=finding.id,
        )
        self._visible_ids.append(finding.id)

    def _refresh_table(self) -> None:
        table = self.query_one("#findings-table", DataTable)
        table.clear()
        self._visible_ids.clear()

        visible = [f for f in self._findings if self._should_display(f)]
        sorted_findings = self._sort_findings(visible)

        for finding in sorted_findings:
            self._add_row(finding)
        self._update_count()

    def _sort_findings(self, findings: list[FindingRow]) -> list[FindingRow]:
        reverse = self.sort_direction == SortDirection.DESC

        if self.sort_column == SortColumn.SEVERITY:
            return sorted(
                findings,
                key=lambda f: SEVERITY_ORDER[f.severity],
                reverse=reverse,
            )
        elif self.sort_column == SortColumn.TYPE:
            return sorted(findings, key=lambda f: f.finding_type, reverse=reverse)
        elif self.sort_column == SortColumn.HOST:
            return sorted(findings, key=lambda f: f.host, reverse=reverse)
        elif self.sort_column == SortColumn.TIMESTAMP:
            return sorted(findings, key=lambda f: f.timestamp, reverse=reverse)
        return findings

    def _update_count(self) -> None:
        count_label = self.query_one("#findings-count", Static)
        total = len(self._findings)
        visible = len(self._visible_ids)
        if visible == total:
            count_label.update(f"{total} findings")
        else:
            count_label.update(f"{visible}/{total} findings")

    def action_cycle_sort(self) -> None:
        columns = list(SortColumn)
        current_idx = columns.index(self.sort_column)
        if self.sort_direction == SortDirection.ASC:
            self.sort_direction = SortDirection.DESC
        else:
            self.sort_direction = SortDirection.ASC
            self.sort_column = columns[(current_idx + 1) % len(columns)]
        self._refresh_table()
        self.app.notify(f"Sorted by {self.sort_column.value} ({self.sort_direction.value})")

    def action_focus_filter(self) -> None:
        filter_input = self.query_one("#type-filter", Input)
        filter_input.focus()

    def action_export_findings(self) -> None:
        self.app.notify("Export: Use export_to_file() method")

    def action_select_finding(self) -> None:
        finding = self.get_selected_finding()
        if finding:
            self.post_message(self.FindingSelected(finding.id))
