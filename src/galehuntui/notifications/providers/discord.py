from __future__ import annotations

from typing import Any, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from galehuntui.notifications.webhook import WebhookEvent

from galehuntui.notifications.providers.base import WebhookProvider


class DiscordProvider(WebhookProvider):
    name = "discord"

    def __init__(
        self,
        webhook_url: str,
        *,
        username: str = "GaleHunTUI",
        avatar_url: str = "",
        **kwargs,
    ) -> None:
        super().__init__(webhook_url, **kwargs)
        self.username = username
        self.avatar_url = avatar_url

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
        embed = self._build_embed(event)

        payload: dict[str, Any] = {
            "username": self.username,
            "embeds": [embed],
        }

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        return payload

    def _build_embed(self, event: WebhookEvent) -> dict[str, Any]:
        title = self._get_event_title(event)
        color = self._get_event_color_int(event)

        embed: dict[str, Any] = {
            "title": title,
            "color": color,
            "timestamp": event.timestamp.isoformat(),
            "footer": {"text": f"Run: {event.run_id[:8]}..."},
        }

        fields = [
            {"name": "Target", "value": event.target, "inline": True},
            {"name": "Event", "value": event.event_type.value, "inline": True},
        ]

        detail_fields = self._get_detail_fields(event)
        fields.extend(detail_fields)

        embed["fields"] = fields

        if event.event_type.value == "finding_discovered":
            severity = event.data.get("severity", "info").upper()
            embed["description"] = f"**{severity}** severity finding detected"

        return embed

    def _get_event_title(self, event: WebhookEvent) -> str:
        emoji_map = {
            "scan_started": ":rocket:",
            "scan_completed": ":white_check_mark:",
            "scan_failed": ":x:",
            "scan_paused": ":pause_button:",
            "scan_resumed": ":arrow_forward:",
            "finding_discovered": ":warning:",
            "stage_started": ":hourglass:",
            "stage_completed": ":checkered_flag:",
            "stage_failed": ":rotating_light:",
        }
        titles = {
            "scan_started": "Scan Started",
            "scan_completed": "Scan Completed",
            "scan_failed": "Scan Failed",
            "scan_paused": "Scan Paused",
            "scan_resumed": "Scan Resumed",
            "finding_discovered": "New Finding",
            "stage_started": "Stage Started",
            "stage_completed": "Stage Completed",
            "stage_failed": "Stage Failed",
        }
        emoji = emoji_map.get(event.event_type.value, ":bell:")
        title = titles.get(event.event_type.value, "Notification")
        return f"{emoji} {title}"

    def _get_event_color_int(self, event: WebhookEvent) -> int:
        if event.event_type.value == "finding_discovered":
            severity = event.data.get("severity", "info")
            hex_color = self.get_severity_color(severity)
        else:
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
            hex_color = color_map.get(event.event_type.value, "#6c757d")

        return int(hex_color.lstrip("#"), 16)

    def _get_detail_fields(self, event: WebhookEvent) -> list[dict[str, Any]]:
        fields = []
        data = event.data

        if event.event_type.value == "scan_started":
            if "profile" in data:
                fields.append({"name": "Profile", "value": data["profile"], "inline": True})
            if "mode" in data:
                fields.append({"name": "Mode", "value": data["mode"], "inline": True})

        elif event.event_type.value == "scan_completed":
            if "duration" in data:
                duration = data["duration"]
                mins = int(duration // 60)
                secs = int(duration % 60)
                fields.append({"name": "Duration", "value": f"{mins}m {secs}s", "inline": True})
            if "findings_count" in data:
                fields.append({"name": "Findings", "value": str(data["findings_count"]), "inline": True})
            if "findings_by_severity" in data:
                severity_lines = [
                    f"**{k.upper()}**: {v}"
                    for k, v in data["findings_by_severity"].items()
                ]
                fields.append({
                    "name": "By Severity",
                    "value": "\n".join(severity_lines) or "None",
                    "inline": False,
                })

        elif event.event_type.value == "scan_failed":
            if "error" in data:
                error_text = data["error"][:500]
                fields.append({"name": "Error", "value": f"```{error_text}```", "inline": False})

        elif event.event_type.value == "finding_discovered":
            if "severity" in data:
                fields.append({"name": "Severity", "value": data["severity"].upper(), "inline": True})
            if "type" in data:
                fields.append({"name": "Type", "value": data["type"], "inline": True})
            if "host" in data:
                fields.append({"name": "Host", "value": data["host"], "inline": True})
            if "title" in data:
                fields.append({"name": "Title", "value": data["title"], "inline": False})
            if "url" in data:
                url = data["url"]
                if len(url) > 100:
                    url = url[:97] + "..."
                fields.append({"name": "URL", "value": f"`{url}`", "inline": False})

        elif event.event_type.value == "stage_completed":
            if "stage" in data:
                fields.append({"name": "Stage", "value": data["stage"], "inline": True})
            if "duration" in data:
                fields.append({"name": "Duration", "value": f"{data['duration']:.1f}s", "inline": True})
            if "findings_count" in data:
                fields.append({"name": "Findings", "value": str(data["findings_count"]), "inline": True})

        return fields
