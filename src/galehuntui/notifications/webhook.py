from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from galehuntui.notifications.providers.base import WebhookProvider

from galehuntui.core.models import Severity


logger = logging.getLogger(__name__)


class EventType(str, Enum):
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"
    SCAN_FAILED = "scan_failed"
    SCAN_PAUSED = "scan_paused"
    SCAN_RESUMED = "scan_resumed"
    FINDING_DISCOVERED = "finding_discovered"
    STAGE_STARTED = "stage_started"
    STAGE_COMPLETED = "stage_completed"
    STAGE_FAILED = "stage_failed"


@dataclass
class WebhookEvent:
    event_type: EventType
    timestamp: datetime
    run_id: str
    target: str
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat(),
            "run_id": self.run_id,
            "target": self.target,
            "data": self.data,
        }


@dataclass
class WebhookConfig:
    enabled: bool = False
    providers: list[str] = field(default_factory=list)
    events: list[EventType] = field(default_factory=lambda: list(EventType))
    min_severity: Severity = Severity.LOW
    rate_limit_per_minute: int = 30
    max_retries: int = 3
    retry_delay_base: float = 1.0
    queue_size: int = 100


@dataclass
class QueuedEvent:
    event: WebhookEvent
    provider_name: str
    attempt: int = 0
    next_retry: Optional[datetime] = None


class WebhookManager:
    def __init__(self, config: WebhookConfig) -> None:
        self.config = config
        self._providers: dict[str, WebhookProvider] = {}
        self._queue: asyncio.Queue[QueuedEvent] = asyncio.Queue(maxsize=config.queue_size)
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
        self._rate_limiter: dict[str, list[datetime]] = {}

    def register_provider(self, name: str, provider: WebhookProvider) -> None:
        self._providers[name] = provider
        self._rate_limiter[name] = []

    def unregister_provider(self, name: str) -> None:
        self._providers.pop(name, None)
        self._rate_limiter.pop(name, None)

    def get_provider(self, name: str) -> Optional[WebhookProvider]:
        return self._providers.get(name)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("Webhook manager started")

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Webhook manager stopped")

    async def emit(self, event: WebhookEvent) -> None:
        if not self.config.enabled:
            return

        if event.event_type not in self.config.events:
            return

        if event.event_type == EventType.FINDING_DISCOVERED:
            severity = event.data.get("severity")
            if severity and not self._meets_severity_threshold(severity):
                return

        for provider_name in self.config.providers:
            if provider_name not in self._providers:
                continue

            queued = QueuedEvent(event=event, provider_name=provider_name)
            try:
                self._queue.put_nowait(queued)
            except asyncio.QueueFull:
                logger.warning(f"Webhook queue full, dropping event: {event.event_type}")

    def emit_sync(self, event: WebhookEvent) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.emit(event))
        except RuntimeError:
            asyncio.run(self.emit(event))

    async def _process_queue(self) -> None:
        while self._running:
            try:
                queued = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if queued.next_retry and datetime.now() < queued.next_retry:
                await self._queue.put(queued)
                await asyncio.sleep(0.1)
                continue

            provider = self._providers.get(queued.provider_name)
            if not provider:
                continue

            if not self._check_rate_limit(queued.provider_name):
                queued.next_retry = datetime.now()
                await self._queue.put(queued)
                await asyncio.sleep(0.5)
                continue

            try:
                await provider.send(queued.event)
                self._record_request(queued.provider_name)
                logger.debug(f"Sent {queued.event.event_type} to {queued.provider_name}")
            except Exception as e:
                queued.attempt += 1
                if queued.attempt < self.config.max_retries:
                    delay = self.config.retry_delay_base * (2 ** queued.attempt)
                    queued.next_retry = datetime.now()
                    await self._queue.put(queued)
                    logger.warning(
                        f"Webhook failed (attempt {queued.attempt}), retrying in {delay}s: {e}"
                    )
                else:
                    logger.error(
                        f"Webhook failed after {self.config.max_retries} attempts: {e}"
                    )

    def _check_rate_limit(self, provider_name: str) -> bool:
        now = datetime.now()
        window_start = now.timestamp() - 60

        requests = self._rate_limiter.get(provider_name, [])
        requests = [r for r in requests if r.timestamp() > window_start]
        self._rate_limiter[provider_name] = requests

        return len(requests) < self.config.rate_limit_per_minute

    def _record_request(self, provider_name: str) -> None:
        if provider_name not in self._rate_limiter:
            self._rate_limiter[provider_name] = []
        self._rate_limiter[provider_name].append(datetime.now())

    def _meets_severity_threshold(self, severity: str | Severity) -> bool:
        if isinstance(severity, str):
            try:
                severity = Severity(severity.lower())
            except ValueError:
                return True

        severity_order = {
            Severity.CRITICAL: 0,
            Severity.HIGH: 1,
            Severity.MEDIUM: 2,
            Severity.LOW: 3,
            Severity.INFO: 4,
        }

        return severity_order.get(severity, 4) <= severity_order.get(self.config.min_severity, 3)

    def create_scan_started_event(
        self,
        run_id: str,
        target: str,
        profile: str,
        mode: str,
    ) -> WebhookEvent:
        return WebhookEvent(
            event_type=EventType.SCAN_STARTED,
            timestamp=datetime.now(),
            run_id=run_id,
            target=target,
            data={"profile": profile, "mode": mode},
        )

    def create_scan_completed_event(
        self,
        run_id: str,
        target: str,
        duration: float,
        findings_count: int,
        findings_by_severity: dict[str, int],
    ) -> WebhookEvent:
        return WebhookEvent(
            event_type=EventType.SCAN_COMPLETED,
            timestamp=datetime.now(),
            run_id=run_id,
            target=target,
            data={
                "duration": duration,
                "findings_count": findings_count,
                "findings_by_severity": findings_by_severity,
            },
        )

    def create_scan_failed_event(
        self,
        run_id: str,
        target: str,
        error: str,
    ) -> WebhookEvent:
        return WebhookEvent(
            event_type=EventType.SCAN_FAILED,
            timestamp=datetime.now(),
            run_id=run_id,
            target=target,
            data={"error": error},
        )

    def create_finding_event(
        self,
        run_id: str,
        target: str,
        finding_id: str,
        severity: str,
        finding_type: str,
        host: str,
        url: str,
        title: str,
    ) -> WebhookEvent:
        return WebhookEvent(
            event_type=EventType.FINDING_DISCOVERED,
            timestamp=datetime.now(),
            run_id=run_id,
            target=target,
            data={
                "finding_id": finding_id,
                "severity": severity,
                "type": finding_type,
                "host": host,
                "url": url,
                "title": title,
            },
        )

    def create_stage_completed_event(
        self,
        run_id: str,
        target: str,
        stage: str,
        duration: float,
        findings_count: int,
    ) -> WebhookEvent:
        return WebhookEvent(
            event_type=EventType.STAGE_COMPLETED,
            timestamp=datetime.now(),
            run_id=run_id,
            target=target,
            data={
                "stage": stage,
                "duration": duration,
                "findings_count": findings_count,
            },
        )
