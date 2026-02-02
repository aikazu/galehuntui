import asyncio
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Header,
    Footer,
    Static,
    Button,
    ProgressBar,
    Label,
    ContentSwitcher,
    LoadingIndicator
)
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual.reactive import reactive
from textual.binding import Binding

class WizardStep(Container):
    """Base class for wizard steps."""
    def __init__(self, id: str, title: str):
        super().__init__(id=id)
        self.title = title

class WelcomeStep(WizardStep):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Welcome to GaleHunTUI Setup", classes="wizard-title"),
            Label(
                "This wizard will help you configure the essential components "
                "for your pentesting workflow.\n\n"
                "We will check your system requirements and install necessary "
                "tools and dependencies.",
                classes="wizard-text"
            ),
            Button("Start Setup", variant="primary", id="start_setup"),
            classes="step-content"
        )

class SystemCheckStep(WizardStep):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("System Check", classes="wizard-title"),
            Label("Verifying environment requirements...", classes="wizard-subtitle"),
            Container(
                Label("Checking Python Version...", id="check_python"),
                Label("Checking Docker...", id="check_docker"),
                Label("Checking Internet Connection...", id="check_net"),
                Label("Checking Write Permissions...", id="check_perms"),
                id="checks_container"
            ),
            Button("Next", variant="primary", id="next_step", disabled=True),
            classes="step-content"
        )

class ToolInstallStep(WizardStep):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Tool Installation", classes="wizard-title"),
            Label("Installing core tools (subfinder, nuclei, httpx...)", classes="wizard-subtitle"),
            ProgressBar(total=100, show_eta=False, id="install_progress"),
            Label("Waiting to start...", id="install_status"),
            Button("Next", variant="primary", id="next_step", disabled=True),
            classes="step-content"
        )

class FinishStep(WizardStep):
    def compose(self) -> ComposeResult:
        yield Vertical(
            Label("Setup Complete!", classes="wizard-title success"),
            Label(
                "You are now ready to start using GaleHunTUI.\n"
                "Documentation is available in the Help screen (Press ?).",
                classes="wizard-text"
            ),
            Button("Open Dashboard", variant="success", id="finish_setup"),
            classes="step-content"
        )

class SetupWizardScreen(Screen):
    """First-run setup wizard."""

    CSS = """
    SetupWizardScreen {
        align: center middle;
    }
    
    .wizard-container {
        width: 60%;
        height: auto;
        min-height: 20;
        border: solid $accent;
        padding: 2;
        background: $surface;
    }

    .wizard-title {
        text-align: center;
        text-style: bold;
        width: 100%;
        margin-bottom: 2;
        color: $accent;
    }
    
    .wizard-subtitle {
        text-align: center;
        color: $text-muted;
        margin-bottom: 1;
    }

    .wizard-text {
        text-align: center;
        margin-bottom: 2;
    }

    .step-content {
        align: center middle;
    }
    
    #checks_container {
        height: auto;
        border: heavy $primary-background;
        padding: 1;
        margin-bottom: 2;
        width: 80%;
    }
    
    #checks_container Label {
        width: 100%;
        padding: 0 1;
    }
    
    ProgressBar {
        width: 80%;
        margin: 2 0;
    }
    
    .success {
        color: $success;
    }
    
    Button {
        margin-top: 2;
    }
    """

    BINDINGS = [
        Binding("escape", "quit_wizard", "Quit Setup"),
    ]

    current_step = reactive("welcome")

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(classes="wizard-container"):
            with ContentSwitcher(initial="welcome"):
                yield WelcomeStep("welcome", "Welcome")
                yield SystemCheckStep("check", "System Check")
                yield ToolInstallStep("install", "Install Tools")
                yield FinishStep("finish", "Finish")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "start_setup":
            self.current_step = "check"
        elif button_id == "next_step":
            if self.current_step == "check":
                self.current_step = "install"
            elif self.current_step == "install":
                self.current_step = "finish"
        elif button_id == "finish_setup":
            self.dismiss(True)

    def watch_current_step(self, step: str) -> None:
        self.query_one(ContentSwitcher).current = step
        if step == "check":
            self.run_checks()
        elif step == "install":
            self.run_install()

    def action_quit_wizard(self) -> None:
        self.app.exit()

    def run_checks(self) -> None:
        """Simulate system checks."""
        async def _check():
            checks = {
                "check_python": "Python 3.11+ ... OK",
                "check_docker": "Docker ... OK",
                "check_net": "Internet ... OK",
                "check_perms": "Permissions ... OK"
            }
            
            for check_id, result in checks.items():
                await asyncio.sleep(0.5)
                lbl = self.query_one(f"#{check_id}", Label)
                lbl.update(f"✅ {result}")
                lbl.styles.color = "green"
            
            self.query_one("#check Button").disabled = False
            self.query_one("#check Button").focus()

        self.run_worker(_check())

    def run_install(self) -> None:
        """Simulate tool installation."""
        async def _install():
            bar = self.query_one(ProgressBar)
            status = self.query_one("#install_status", Label)
            
            tools = ["subfinder", "dnsx", "httpx", "nuclei", "dalfox", "ffuf"]
            step_size = 100 / len(tools)
            
            for tool in tools:
                status.update(f"Installing {tool}...")
                # Simulate work
                await asyncio.sleep(0.8)
                bar.advance(step_size)
            
            status.update("All tools installed successfully!")
            status.styles.color = "green"
            self.query_one("#install Button").disabled = False
            self.query_one("#install Button").focus()

        self.run_worker(_install())
