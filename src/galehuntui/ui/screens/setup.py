import asyncio
import sys
import shutil
import os
from pathlib import Path
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

from galehuntui.tools.installer import ToolInstaller
from galehuntui.core.config import get_data_dir, get_config_dir

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
                Label("Checking Git...", id="check_git"),
                Label("Checking Docker...", id="check_docker"),
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
            Label("Installing core tools from registry...", classes="wizard-subtitle"),
            ProgressBar(total=100, show_eta=True, id="install_progress"),
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
        """Perform real system checks."""
        async def _check():
            # Check Python
            py_ver = sys.version_info
            py_ok = py_ver >= (3, 11)
            py_lbl = self.query_one("#check_python", Label)
            if py_ok:
                py_lbl.update(f"✅ Python {py_ver.major}.{py_ver.minor} detected")
                py_lbl.styles.color = "green"
            else:
                py_lbl.update(f"❌ Python {py_ver.major}.{py_ver.minor} (Need 3.11+)")
                py_lbl.styles.color = "red"
            await asyncio.sleep(0.1)
            
            # Check Git
            git_path = shutil.which("git")
            git_lbl = self.query_one("#check_git", Label)
            git_ok = bool(git_path)
            if git_ok:
                git_lbl.update(f"✅ Git detected ({git_path})")
                git_lbl.styles.color = "green"
            else:
                git_lbl.update("❌ Git not found")
                git_lbl.styles.color = "red"
            await asyncio.sleep(0.1)

            # Check Docker
            docker_path = shutil.which("docker")
            docker_lbl = self.query_one("#check_docker", Label)
            if docker_path:
                docker_lbl.update("✅ Docker available")
                docker_lbl.styles.color = "green"
            else:
                docker_lbl.update("⚠️ Docker not found (recommended)")
                docker_lbl.styles.color = "yellow"
            await asyncio.sleep(0.1)
            
            # Check Write Permissions
            perm_lbl = self.query_one("#check_perms", Label)
            data_dir = get_data_dir()
            try:
                data_dir.mkdir(parents=True, exist_ok=True)
                if os.access(data_dir, os.W_OK):
                    perm_lbl.update(f"✅ Write access to {data_dir}")
                    perm_lbl.styles.color = "green"
                    perm_ok = True
                else:
                    raise PermissionError
            except Exception:
                perm_lbl.update(f"❌ No write access to {data_dir}")
                perm_lbl.styles.color = "red"
                perm_ok = False
            
            if py_ok and git_ok and perm_ok:
                self.query_one("#check Button").disabled = False
                self.query_one("#check Button").focus()

        self.run_worker(_check())

    def run_install(self) -> None:
        """Run real tool installation."""
        async def _install():
            bar = self.query_one(ProgressBar)
            status = self.query_one("#install_status", Label)
            btn = self.query_one("#install Button")
            
            # Initialize ToolInstaller
            # tools/ directory relative to project root
            try:
                tools_dir = get_config_dir().parent / "tools"
                installer = ToolInstaller(tools_dir)
                
                # Load registry
                registry = installer.load_registry()
                tools = list(registry.get("tools", {}).keys())
            except Exception as e:
                status.update(f"❌ Initialization failed: {e}")
                status.styles.color = "red"
                return

            if not tools:
                status.update("⚠️ No tools found in registry.")
                btn.disabled = False
                return

            bar.update(total=len(tools), progress=0)
            
            failed = []
            for tool in tools:
                status.update(f"Installing {tool}...")
                try:
                    await installer.install_tool(tool)
                    # Verify
                    if not installer.verify_tool(tool):
                        failed.append(f"{tool} (verification failed)")
                except Exception as e:
                    failed.append(f"{tool} ({str(e)})")
                
                bar.advance(1)
            
            if failed:
                status.update(f"⚠️ Installed with errors: {len(failed)} failed")
                status.styles.color = "yellow"
            else:
                status.update("✅ All tools installed successfully!")
                status.styles.color = "green"
            
            btn.disabled = False
            btn.focus()

        self.run_worker(_install())
