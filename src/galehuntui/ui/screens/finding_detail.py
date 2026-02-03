from typing import List, Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    Markdown,
    Static,
    TabbedContent,
    TabPane,
)

from galehuntui.core.models import Finding, Severity, Confidence


class FindingDetailScreen(Screen):
    """Screen for viewing detailed information about a specific finding."""

    CSS = """
    FindingDetailScreen {
        layout: vertical;
    }

    #finding-container {
        height: 1fr;
        padding: 1 2;
    }

    /* Summary Bar */
    .summary-bar {
        height: 3;
        dock: top;
        margin-bottom: 1;
        background: #1a1c29;
        border: solid #2e344d;
        padding: 0 1;
        align-y: middle;
    }

    .badge {
        padding: 0 1;
        margin-right: 1;
        text-style: bold;
        color: #0f111a;
        background: #64748b;
    }

    .badge-critical { background: #ff3333; color: white; }
    .badge-high { background: #ff3333; opacity: 80%; color: white; }
    .badge-medium { background: #ffb700; color: #0f111a; }
    .badge-low { background: #00ff9d; color: #0f111a; }
    .badge-info { background: #00f2ea; color: #0f111a; }

    .meta-item {
        margin-right: 2;
        color: #64748b;
    }
    
    .meta-value {
        color: #e2e8f0;
        text-style: bold;
    }

    /* Main Content Layout */
    .content-area {
        height: 1fr;
    }

    /* Sidebar Details */
    .sidebar {
        width: 30%;
        height: 100%;
        border-right: solid #2e344d;
        padding-right: 1;
        background: #0f111a;
    }

    .detail-group {
        margin-bottom: 1;
    }

    .detail-label {
        color: #00f2ea;
        text-style: bold;
    }

    .detail-value {
        color: #e2e8f0;
    }

    /* Main Tab Area */
    .main-tabs {
        width: 70%;
        height: 100%;
        padding-left: 1;
    }
    
    Markdown {
        padding: 1;
        background: #0f111a;
    }
    
    .evidence-item {
        padding: 1;
        border: solid #2e344d;
        margin-bottom: 1;
        background: #1a1c29;
    }
    """

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
        Binding("n", "next_finding", "Next Finding"),
        Binding("p", "prev_finding", "Previous Finding"),
    ]

    def __init__(
        self,
        findings: Optional[List[Finding]] = None,
        initial_index: int = 0,
        name: Optional[str] = None,
        id: Optional[str] = None,
        classes: Optional[str] = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.findings = findings or []
        self.current_index = max(0, min(initial_index, len(self.findings) - 1)) if self.findings else 0

    def get_current_finding(self) -> Optional[Finding]:
        if not self.findings:
            return None
        return self.findings[self.current_index]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        
        with Container(id="finding-container"):
            # Top Summary Bar
            with Horizontal(classes="summary-bar"):
                yield Static(id="severity-badge", classes="badge")
                yield Static(id="confidence-badge", classes="badge")
                yield Label("Tool: ", classes="meta-item")
                yield Label("", id="tool-name", classes="meta-value")
                yield Label("Type: ", classes="meta-item")
                yield Label("", id="vuln-type", classes="meta-value")

            # Main Content Split
            with Horizontal(classes="content-area"):
                # Left Sidebar
                with Vertical(classes="sidebar"):
                    with VerticalScroll():
                        self._detail_item("ID", "id-value")
                        self._detail_item("Host", "host-value")
                        self._detail_item("URL", "url-value")
                        self._detail_item("Parameter", "param-value")
                        self._detail_item("Timestamp", "time-value")
                        self._detail_item("Run ID", "run-id-value")

                # Right Content
                with TabbedContent(classes="main-tabs"):
                    with TabPane("Overview"):
                        yield Markdown(id="md-description")
                        yield Markdown(id="md-remediation")
                    
                    with TabPane("Evidence"):
                        yield VerticalScroll(id="evidence-list")
                    
                    with TabPane("Reproduction"):
                        yield Markdown(id="md-reproduction")
                        
                    with TabPane("Raw Data"):
                         yield Markdown(id="md-raw")

        yield Footer()

    def _detail_item(self, label: str, id_value: str) -> ComposeResult:
        with Vertical(classes="detail-group"):
            yield Label(label, classes="detail-label")
            yield Label("", id=id_value, classes="detail-value")

    def on_mount(self) -> None:
        """Load initial data."""
        self.update_view()

    def action_next_finding(self) -> None:
        """Show next finding."""
        if self.current_index < len(self.findings) - 1:
            self.current_index += 1
            self.update_view()
        else:
            self.notify("End of findings list")

    def action_prev_finding(self) -> None:
        """Show previous finding."""
        if self.current_index > 0:
            self.current_index -= 1
            self.update_view()
        else:
            self.notify("Start of findings list")

    def update_view(self) -> None:
        """Update all widgets with current finding data."""
        finding = self.get_current_finding()
        if not finding:
            return

        self.title = f"Finding: {finding.title}"
        self.sub_title = f"{self.current_index + 1} of {len(self.findings)}"

        # Summary Bar
        sev_badge = self.query_one("#severity-badge", Static)
        sev_badge.update(finding.severity.value.upper())
        sev_badge.classes = f"badge badge-{finding.severity.value.lower()}"

        conf_badge = self.query_one("#confidence-badge", Static)
        conf_badge.update(finding.confidence.value.upper())
        # Re-use severity colors or add specific confidence styles if needed
        # For now, just generic badge style or maybe map confirmation to success/warning
        
        self.query_one("#tool-name", Label).update(finding.tool)
        self.query_one("#vuln-type", Label).update(finding.type)

        # Sidebar Details
        self.query_one("#id-value", Label).update(str(finding.id))
        self.query_one("#host-value", Label).update(finding.host)
        self.query_one("#url-value", Label).update(finding.url)
        self.query_one("#param-value", Label).update(finding.parameter or "N/A")
        self.query_one("#time-value", Label).update(str(finding.timestamp))
        self.query_one("#run-id-value", Label).update(str(finding.run_id))

        # Markdown Content
        desc_md = f"## Description\n\n{finding.description or 'No description provided.'}"
        self.query_one("#md-description", Markdown).update(desc_md)

        rem_md = f"## Remediation\n\n{finding.remediation or 'No remediation steps provided.'}"
        if finding.references:
            rem_md += "\n\n### References\n" + "\n".join(f"- {ref}" for ref in finding.references)
        self.query_one("#md-remediation", Markdown).update(rem_md)

        # Evidence
        evidence_container = self.query_one("#evidence-list", VerticalScroll)
        evidence_container.remove_children()
        
        if finding.evidence_paths:
            for path in finding.evidence_paths:
                evidence_container.mount(
                    Label(f"📄 {path}", classes="evidence-item")
                )
        else:
            evidence_container.mount(Label("No evidence files attached.", classes="text-muted"))

        # Reproduction
        if finding.reproduction_steps:
            steps_md = "## Steps to Reproduce\n\n" + "\n".join(f"{i+1}. {step}" for i, step in enumerate(finding.reproduction_steps))
            self.query_one("#md-reproduction", Markdown).update(steps_md)
        else:
            self.query_one("#md-reproduction", Markdown).update("_No reproduction steps provided._")

        # Raw Data (Placeholder if we don't have direct access to raw output content here)
        self.query_one("#md-raw", Markdown).update(f"```json\n{finding}\n```")
