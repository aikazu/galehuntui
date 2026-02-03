from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from galehuntui.notifications.webhook import WebhookEvent


class WebhookProvider(ABC):
    name: str = "base"

    def __init__(self, webhook_url: str, **kwargs) -> None:
        self.webhook_url = webhook_url
        self.options = kwargs

    @abstractmethod
    async def send(self, event: WebhookEvent) -> None:
        pass

    @abstractmethod
    def format_message(self, event: WebhookEvent) -> dict:
        pass

    def get_severity_color(self, severity: str) -> str:
        colors = {
            "critical": "#dc3545",
            "high": "#fd7e14",
            "medium": "#ffc107",
            "low": "#17a2b8",
            "info": "#6c757d",
        }
        return colors.get(severity.lower(), "#6c757d")

    def get_event_emoji(self, event_type: str) -> str:
        emojis = {
            "scan_started": ":rocket:",
            "scan_completed": ":white_check_mark:",
            "scan_failed": ":x:",
            "scan_paused": ":pause_button:",
            "scan_resumed": ":arrow_forward:",
            "finding_discovered": ":warning:",
            "stage_started": ":hourglass_flowing_sand:",
            "stage_completed": ":checkered_flag:",
            "stage_failed": ":rotating_light:",
        }
        return emojis.get(event_type, ":bell:")
