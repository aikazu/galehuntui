from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, RichLog, Select, Static


class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


LOG_LEVEL_PRIORITY = {
    LogLevel.DEBUG: 0,
    LogLevel.INFO: 1,
    LogLevel.WARNING: 2,
    LogLevel.ERROR: 3,
    LogLevel.CRITICAL: 4,
}

LOG_LEVEL_COLORS = {
    LogLevel.DEBUG: "dim",
    LogLevel.INFO: "blue",
    LogLevel.WARNING: "yellow",
    LogLevel.ERROR: "red",
    LogLevel.CRITICAL: "red bold",
}


@dataclass
class LogEntry:
    timestamp: datetime
    level: LogLevel
    message: str
    source: str = ""


class LogViewWidget(Widget):
    DEFAULT_CSS = """
    LogViewWidget {
        layout: vertical;
        height: 100%;
    }
    LogViewWidget .log-toolbar {
        height: 3;
        background: #1a1c29;
        padding: 0 1;
    }
    LogViewWidget .log-toolbar Select {
        width: 20;
        margin-right: 1;
    }
    LogViewWidget .log-toolbar Input {
        width: 1fr;
    }
    LogViewWidget .log-toolbar Static {
        width: auto;
        padding: 0 1;
        content-align: center middle;
    }
    LogViewWidget RichLog {
        height: 1fr;
        border: solid #2e344d;
        background: #0f111a;
    }
    """

    BINDINGS = [
        Binding("ctrl+f", "focus_search", "Search"),
        Binding("ctrl+e", "export_logs", "Export"),
        Binding("ctrl+l", "clear_logs", "Clear"),
    ]

    min_level: reactive[LogLevel] = reactive(LogLevel.DEBUG)
    search_query: reactive[str] = reactive("")

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._entries: list[LogEntry] = []
        self._filtered_count = 0

    def compose(self) -> ComposeResult:
        with Horizontal(classes="log-toolbar"):
            yield Select(
                [(level.value.upper(), level.value) for level in LogLevel],
                value=LogLevel.DEBUG.value,
                id="log-level-filter",
            )
            yield Input(placeholder="Search logs...", id="log-search")
            yield Static("0 entries", id="log-count")
        yield RichLog(highlight=True, markup=True, id="log-output")

    def on_mount(self) -> None:
        self._update_count_display()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "log-level-filter":
            self.min_level = LogLevel(event.value)
            self._refresh_display()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "log-search":
            self.search_query = event.value
            self._refresh_display()

    def add_entry(self, entry: LogEntry) -> None:
        self._entries.append(entry)
        if self._should_display(entry):
            self._write_entry(entry)
            self._filtered_count += 1
            self._update_count_display()

    def write(
        self,
        message: str,
        level: LogLevel = LogLevel.INFO,
        source: str = "",
    ) -> None:
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            message=message,
            source=source,
        )
        self.add_entry(entry)

    def write_info(self, message: str, source: str = "") -> None:
        self.write(message, LogLevel.INFO, source)

    def write_warning(self, message: str, source: str = "") -> None:
        self.write(message, LogLevel.WARNING, source)

    def write_error(self, message: str, source: str = "") -> None:
        self.write(message, LogLevel.ERROR, source)

    def write_debug(self, message: str, source: str = "") -> None:
        self.write(message, LogLevel.DEBUG, source)

    def write_critical(self, message: str, source: str = "") -> None:
        self.write(message, LogLevel.CRITICAL, source)

    def clear(self) -> None:
        self._entries.clear()
        self._filtered_count = 0
        log_output = self.query_one("#log-output", RichLog)
        log_output.clear()
        self._update_count_display()

    def export_to_file(self, path: Path) -> int:
        exported = 0
        with path.open("w") as f:
            for entry in self._entries:
                if self._should_display(entry):
                    line = self._format_entry_plain(entry)
                    f.write(line + "\n")
                    exported += 1
        return exported

    def get_visible_entries(self) -> list[LogEntry]:
        return [e for e in self._entries if self._should_display(e)]

    def _should_display(self, entry: LogEntry) -> bool:
        if LOG_LEVEL_PRIORITY[entry.level] < LOG_LEVEL_PRIORITY[self.min_level]:
            return False
        if self.search_query:
            query_lower = self.search_query.lower()
            if query_lower not in entry.message.lower():
                return False
        return True

    def _write_entry(self, entry: LogEntry) -> None:
        log_output = self.query_one("#log-output", RichLog)
        formatted = self._format_entry(entry)
        log_output.write(formatted)

    def _format_entry(self, entry: LogEntry) -> str:
        timestamp = entry.timestamp.strftime("%H:%M:%S")
        color = LOG_LEVEL_COLORS[entry.level]
        level_str = entry.level.value.upper()[:4]
        source_str = f" [{entry.source}]" if entry.source else ""
        return f"[dim]{timestamp}[/] [{color}]{level_str}[/]{source_str} {entry.message}"

    def _format_entry_plain(self, entry: LogEntry) -> str:
        timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        level_str = entry.level.value.upper()
        source_str = f" [{entry.source}]" if entry.source else ""
        return f"{timestamp} {level_str}{source_str} {entry.message}"

    def _refresh_display(self) -> None:
        log_output = self.query_one("#log-output", RichLog)
        log_output.clear()
        self._filtered_count = 0
        for entry in self._entries:
            if self._should_display(entry):
                self._write_entry(entry)
                self._filtered_count += 1
        self._update_count_display()

    def _update_count_display(self) -> None:
        count_label = self.query_one("#log-count", Static)
        total = len(self._entries)
        if self._filtered_count == total:
            count_label.update(f"{total} entries")
        else:
            count_label.update(f"{self._filtered_count}/{total} entries")

    def action_focus_search(self) -> None:
        search_input = self.query_one("#log-search", Input)
        search_input.focus()

    def action_export_logs(self) -> None:
        self.app.notify("Export: Use export_to_file() method")

    def action_clear_logs(self) -> None:
        self.clear()
        self.app.notify("Logs cleared")
