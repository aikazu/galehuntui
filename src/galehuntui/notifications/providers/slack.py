from __future__ import annotations

import json
from typing import Any, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from galehuntui.notifications.webhook import WebhookEvent

from galehuntui.notifications.providers.base import WebhookProvider


class SlackProvider(WebhookProvider):
    name = "slack"

    def __init__(
        self,
        webhook_url: str,
        *,
        channel: str = "",
        username: str = "GaleHunTUI",
        icon_emoji: str = ":shield:",
        **kwargs,
    ) -> None:
        super().__init__(webhook_url, **kwargs)
        self.channel = channel
        self.username = username
        self.icon_emoji = icon_emoji

    async def send(self, event: WebhookEvent) -> None:
        payload = self.format_message(event)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()

    def format_message(self, event: WebhookEvent) -> dict[str, Any]:
        emoji = self.get_event_emoji(event.event_type.value)
        title = self._get_event_title(event)
        color = self._get_event_color(event)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Target:*\n{event.target}"},
                    {"type": "mrkdwn", "text": f"*Run ID:*\n`{event.run_id[:8]}...`"},
                ],
            },
        ]

        detail_fields = self._get_detail_fields(event)
        if detail_fields:
            blocks.append({
                "type": "section",
                "fields": detail_fields,
            })

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f":clock1: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
                },
            ],
        })

        attachment = {
            "color": color,
            "blocks": blocks,
        }

        payload: dict[str, Any] = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [attachment],
        }

        if self.channel:
            payload["channel"] = self.channel

        return payload

    def _get_event_title(self, event: WebhookEvent) -> str:
        titles = {
            "scan_started": "Scan Started",
            "scan_completed": "Scan Completed",
            "scan_failed": "Scan Failed",
            "scan_paused": "Scan Paused",
            "scan_resumed": "Scan Resumed",
            "finding_discovered": "New Finding Discovered",
            "stage_started": "Stage Started",
            "stage_completed": "Stage Completed",
            "stage_failed": "Stage Failed",
        }
        return titles.get(event.event_type.value, "Notification")

    def _get_event_color(self, event: WebhookEvent) -> str:
        if event.event_type.value == "finding_discovered":
            severity = event.data.get("severity", "info")
            return self.get_severity_color(severity)

        color_map = {
            "scan_started": "#17a2b8",
            "scan_completed": "#28a745",
            "scan_failed": "#dc3545",
            "scan_paused": "#ffc107",
            "scan_resumed": "#17a2b8",
            "stage_started": "#6c757d",
            "stage_completed": "#28a745",
            "stage_failed": "#dc3545",
        }
        return color_map.get(event.event_type.value, "#6c757d")

    def _get_detail_fields(self, event: WebhookEvent) -> list[dict[str, str]]:
        fields = []
        data = event.data

        if event.event_type.value == "scan_started":
            if "profile" in data:
                fields.append({"type": "mrkdwn", "text": f"*Profile:*\n{data['profile']}"})
            if "mode" in data:
                fields.append({"type": "mrkdwn", "text": f"*Mode:*\n{data['mode']}"})

        elif event.event_type.value == "scan_completed":
            if "duration" in data:
                duration = data["duration"]
                mins = int(duration // 60)
                secs = int(duration % 60)
                fields.append({"type": "mrkdwn", "text": f"*Duration:*\n{mins}m {secs}s"})
            if "findings_count" in data:
                fields.append({"type": "mrkdwn", "text": f"*Findings:*\n{data['findings_count']}"})
            if "findings_by_severity" in data:
                severity_text = ", ".join(
                    f"{k}: {v}" for k, v in data["findings_by_severity"].items()
                )
                fields.append({"type": "mrkdwn", "text": f"*By Severity:*\n{severity_text}"})

        elif event.event_type.value == "scan_failed":
            if "error" in data:
                fields.append({"type": "mrkdwn", "text": f"*Error:*\n```{data['error'][:200]}```"})

        elif event.event_type.value == "finding_discovered":
            if "severity" in data:
                severity = data["severity"].upper()
                fields.append({"type": "mrkdwn", "text": f"*Severity:*\n{severity}"})
            if "type" in data:
                fields.append({"type": "mrkdwn", "text": f"*Type:*\n{data['type']}"})
            if "host" in data:
                fields.append({"type": "mrkdwn", "text": f"*Host:*\n{data['host']}"})
            if "title" in data:
                fields.append({"type": "mrkdwn", "text": f"*Title:*\n{data['title']}"})

        elif event.event_type.value == "stage_completed":
            if "stage" in data:
                fields.append({"type": "mrkdwn", "text": f"*Stage:*\n{data['stage']}"})
            if "duration" in data:
                fields.append({"type": "mrkdwn", "text": f"*Duration:*\n{data['duration']:.1f}s"})
            if "findings_count" in data:
                fields.append({"type": "mrkdwn", "text": f"*Findings:*\n{data['findings_count']}"})

        return fields
