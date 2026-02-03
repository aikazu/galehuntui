from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ProgressBar, Static

from galehuntui.core.constants import StepStatus


STATUS_ICONS = {
    StepStatus.PENDING: "[dim]○[/]",
    StepStatus.RUNNING: "[cyan]●[/]",
    StepStatus.COMPLETED: "[green]✓[/]",
    StepStatus.FAILED: "[red]✗[/]",
    StepStatus.SKIPPED: "[yellow]−[/]",
}


@dataclass
class StageInfo:
    name: str
    display_name: str
    status: StepStatus = StepStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration: float = 0.0
    findings_count: int = 0


class StageRow(Widget):
    DEFAULT_CSS = """
    StageRow {
        layout: horizontal;
        height: 1;
        padding: 0 1;
    }
    StageRow:hover {
        background: $surface-lighter;
    }
    StageRow .stage-icon {
        width: 3;
        text-align: center;
    }
    StageRow .stage-name {
        width: 1fr;
    }
    StageRow .stage-status {
        width: 12;
        text-align: center;
    }
    StageRow .stage-duration {
        width: 10;
        text-align: right;
    }
    StageRow .stage-findings {
        width: 8;
        text-align: right;
    }
    StageRow.running {
        background: $surface-light;
    }
    StageRow.completed .stage-name {
        color: $success;
    }
    StageRow.failed .stage-name {
        color: $error;
    }
    """

    def __init__(self, stage: StageInfo) -> None:
        super().__init__()
        self.stage = stage
        self._update_classes()

    def compose(self) -> ComposeResult:
        yield Static(STATUS_ICONS[self.stage.status], classes="stage-icon")
        yield Static(self.stage.display_name, classes="stage-name")
        yield Static(self._format_status(), classes="stage-status")
        yield Static(self._format_duration(), classes="stage-duration")
        yield Static(self._format_findings(), classes="stage-findings")

    def update_stage(self, stage: StageInfo) -> None:
        self.stage = stage
        self._update_classes()
        self._refresh_content()

    def _update_classes(self) -> None:
        self.remove_class("pending", "running", "completed", "failed", "skipped")
        self.add_class(self.stage.status.value)

    def _refresh_content(self) -> None:
        self.query_one(".stage-icon", Static).update(STATUS_ICONS[self.stage.status])
        self.query_one(".stage-status", Static).update(self._format_status())
        self.query_one(".stage-duration", Static).update(self._format_duration())
        self.query_one(".stage-findings", Static).update(self._format_findings())

    def _format_status(self) -> str:
        status_labels = {
            StepStatus.PENDING: "[dim]Pending[/]",
            StepStatus.RUNNING: "[cyan]Running...[/]",
            StepStatus.COMPLETED: "[green]Done[/]",
            StepStatus.FAILED: "[red]Failed[/]",
            StepStatus.SKIPPED: "[yellow]Skipped[/]",
        }
        return status_labels[self.stage.status]

    def _format_duration(self) -> str:
        if self.stage.status == StepStatus.PENDING:
            return "[dim]--[/]"
        if self.stage.status == StepStatus.RUNNING:
            if self.stage.started_at:
                elapsed = (datetime.now() - self.stage.started_at).total_seconds()
                return self._format_seconds(elapsed)
            return "[cyan]...[/]"
        return self._format_seconds(self.stage.duration)

    def _format_findings(self) -> str:
        if self.stage.findings_count == 0:
            return "[dim]0[/]"
        return f"[yellow]{self.stage.findings_count}[/]"

    def _format_seconds(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m{secs}s"


class PipelineProgressWidget(Widget):
    DEFAULT_CSS = """
    PipelineProgressWidget {
        layout: vertical;
        height: auto;
        min-height: 10;
        border: solid $border;
        background: $surface;
    }
    PipelineProgressWidget .progress-header {
        height: 3;
        background: $surface-light;
        padding: 0 1;
        border-bottom: solid $border;
    }
    PipelineProgressWidget .progress-header Label {
        width: 1fr;
        content-align: left middle;
    }
    PipelineProgressWidget .progress-header Static {
        width: auto;
        content-align: right middle;
        padding: 0 1;
    }
    PipelineProgressWidget .progress-bar-container {
        height: 1;
        padding: 0 1;
        margin-bottom: 1;
    }
    PipelineProgressWidget .stages-header {
        height: 1;
        background: $surface-light;
        padding: 0 1;
    }
    PipelineProgressWidget .stages-header Static {
        text-style: bold;
    }
    PipelineProgressWidget .stages-list {
        height: auto;
        max-height: 20;
    }
    PipelineProgressWidget .header-icon {
        width: 3;
        text-align: center;
    }
    PipelineProgressWidget .header-name {
        width: 1fr;
    }
    PipelineProgressWidget .header-status {
        width: 12;
        text-align: center;
    }
    PipelineProgressWidget .header-duration {
        width: 10;
        text-align: right;
    }
    PipelineProgressWidget .header-findings {
        width: 8;
        text-align: right;
    }
    """

    total_stages: reactive[int] = reactive(0)
    completed_stages: reactive[int] = reactive(0)

    def __init__(
        self,
        *,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._stages: dict[str, StageInfo] = {}
        self._stage_order: list[str] = []
        self._start_time: Optional[datetime] = None

    def compose(self) -> ComposeResult:
        with Horizontal(classes="progress-header"):
            yield Label("Pipeline Progress", classes="progress-title")
            yield Static("0/0 stages", id="stage-count")
            yield Static("00:00", id="elapsed-time")

        with Horizontal(classes="progress-bar-container"):
            yield ProgressBar(total=100, show_eta=False, id="overall-progress")

        with Horizontal(classes="stages-header"):
            yield Static("", classes="header-icon")
            yield Static("Stage", classes="header-name")
            yield Static("Status", classes="header-status")
            yield Static("Duration", classes="header-duration")
            yield Static("Finds", classes="header-findings")

        yield Vertical(id="stages-list", classes="stages-list")

    def on_mount(self) -> None:
        self.set_interval(1.0, self._update_elapsed)

    def register_stages(self, stages: list[tuple[str, str]]) -> None:
        self._stage_order = []
        self._stages = {}
        stages_list = self.query_one("#stages-list", Vertical)
        stages_list.remove_children()

        for name, display_name in stages:
            stage = StageInfo(name=name, display_name=display_name)
            self._stages[name] = stage
            self._stage_order.append(name)
            stages_list.mount(StageRow(stage))

        self.total_stages = len(stages)
        self._update_progress()

    def start_pipeline(self) -> None:
        self._start_time = datetime.now()

    def start_stage(self, name: str) -> None:
        if name not in self._stages:
            return
        stage = self._stages[name]
        stage.status = StepStatus.RUNNING
        stage.started_at = datetime.now()
        self._update_stage_row(name)

    def complete_stage(
        self,
        name: str,
        *,
        findings_count: int = 0,
        duration: Optional[float] = None,
    ) -> None:
        if name not in self._stages:
            return
        stage = self._stages[name]
        stage.status = StepStatus.COMPLETED
        stage.completed_at = datetime.now()
        stage.findings_count = findings_count
        if duration is not None:
            stage.duration = duration
        elif stage.started_at:
            stage.duration = (stage.completed_at - stage.started_at).total_seconds()
        self.completed_stages += 1
        self._update_stage_row(name)
        self._update_progress()

    def fail_stage(self, name: str, duration: Optional[float] = None) -> None:
        if name not in self._stages:
            return
        stage = self._stages[name]
        stage.status = StepStatus.FAILED
        stage.completed_at = datetime.now()
        if duration is not None:
            stage.duration = duration
        elif stage.started_at:
            stage.duration = (stage.completed_at - stage.started_at).total_seconds()
        self._update_stage_row(name)

    def skip_stage(self, name: str) -> None:
        if name not in self._stages:
            return
        stage = self._stages[name]
        stage.status = StepStatus.SKIPPED
        self._update_stage_row(name)

    def get_stage(self, name: str) -> Optional[StageInfo]:
        return self._stages.get(name)

    def _update_stage_row(self, name: str) -> None:
        if name not in self._stages:
            return
        idx = self._stage_order.index(name)
        stages_list = self.query_one("#stages-list", Vertical)
        rows = list(stages_list.query(StageRow))
        if idx < len(rows):
            rows[idx].update_stage(self._stages[name])

    def _update_progress(self) -> None:
        count_label = self.query_one("#stage-count", Static)
        count_label.update(f"{self.completed_stages}/{self.total_stages} stages")

        progress_bar = self.query_one("#overall-progress", ProgressBar)
        if self.total_stages > 0:
            pct = (self.completed_stages / self.total_stages) * 100
            progress_bar.update(progress=pct)

    def _update_elapsed(self) -> None:
        if not self._start_time:
            return
        elapsed = (datetime.now() - self._start_time).total_seconds()
        elapsed_label = self.query_one("#elapsed-time", Static)
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        elapsed_label.update(f"{mins:02d}:{secs:02d}")

        for name, stage in self._stages.items():
            if stage.status == StepStatus.RUNNING:
                self._update_stage_row(name)
