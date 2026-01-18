"""Logging and observability for Anvil SDK."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class EventType(Enum):
    """Types of events that can be logged."""

    TOOL_GENERATED = "tool_generated"
    TOOL_LOADED = "tool_loaded"
    TOOL_EXECUTED = "tool_executed"
    TOOL_FAILED = "tool_failed"
    TOOL_HEALED = "tool_healed"
    CHAIN_STARTED = "chain_started"
    CHAIN_COMPLETED = "chain_completed"
    CHAIN_FAILED = "chain_failed"


@dataclass
class AnvilEvent:
    """A logged event from Anvil operations."""

    timestamp: datetime
    event_type: EventType
    tool_name: str
    duration_ms: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "tool_name": self.tool_name,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnvilEvent:
        """Create event from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=EventType(data["event_type"]),
            tool_name=data["tool_name"],
            duration_ms=data.get("duration_ms"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


class AnvilLogger:
    """Logger for tracking Anvil SDK operations.

    Stores events in memory and optionally writes to a file.
    Provides query methods for analyzing tool execution history.

    Example:
        logger = AnvilLogger(log_file="./anvil.log")

        # Log an event
        logger.log(AnvilEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_EXECUTED,
            tool_name="search_notion",
            duration_ms=150.5,
        ))

        # Query history
        events = logger.get_history(tool_name="search_notion")
        stats = logger.get_stats("search_notion")
    """

    def __init__(self, log_file: Path | str | None = None):
        """Initialize the logger.

        Args:
            log_file: Optional path to write logs to (JSON lines format)
        """
        self.events: list[AnvilEvent] = []
        self.log_file = Path(log_file) if log_file else None

        # Ensure log directory exists
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: AnvilEvent) -> None:
        """Log an event.

        Args:
            event: The event to log
        """
        self.events.append(event)

        if self.log_file:
            self._write_to_file(event)

    def _write_to_file(self, event: AnvilEvent) -> None:
        """Append event to log file in JSON lines format."""
        with open(self.log_file, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

    def get_history(
        self,
        tool_name: str | None = None,
        event_type: EventType | None = None,
        since: datetime | None = None,
        limit: int | None = None,
    ) -> list[AnvilEvent]:
        """Get event history with optional filters.

        Args:
            tool_name: Filter by tool name
            event_type: Filter by event type
            since: Only events after this timestamp
            limit: Maximum number of events to return

        Returns:
            List of matching events (newest first)
        """
        filtered = self.events

        if tool_name:
            filtered = [e for e in filtered if e.tool_name == tool_name]

        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]

        if since:
            filtered = [e for e in filtered if e.timestamp >= since]

        # Sort newest first
        filtered = sorted(filtered, key=lambda e: e.timestamp, reverse=True)

        if limit:
            filtered = filtered[:limit]

        return filtered

    def get_stats(self, tool_name: str) -> dict[str, Any]:
        """Get execution statistics for a tool.

        Args:
            tool_name: The tool to get stats for

        Returns:
            Dict with execution count, success rate, avg duration, etc.
        """
        tool_events = [e for e in self.events if e.tool_name == tool_name]

        executions = [e for e in tool_events if e.event_type == EventType.TOOL_EXECUTED]
        failures = [e for e in tool_events if e.event_type == EventType.TOOL_FAILED]
        heals = [e for e in tool_events if e.event_type == EventType.TOOL_HEALED]

        durations = [e.duration_ms for e in executions if e.duration_ms is not None]

        total = len(executions) + len(failures)
        success_rate = len(executions) / total if total > 0 else 0.0

        return {
            "tool_name": tool_name,
            "total_executions": total,
            "successful": len(executions),
            "failed": len(failures),
            "healed": len(heals),
            "success_rate": success_rate,
            "avg_duration_ms": sum(durations) / len(durations) if durations else None,
            "min_duration_ms": min(durations) if durations else None,
            "max_duration_ms": max(durations) if durations else None,
        }

    def get_recent_errors(self, limit: int = 10) -> list[AnvilEvent]:
        """Get the most recent error events.

        Args:
            limit: Maximum number of errors to return

        Returns:
            List of error events (newest first)
        """
        return self.get_history(event_type=EventType.TOOL_FAILED, limit=limit)

    def clear(self) -> None:
        """Clear all logged events from memory."""
        self.events.clear()

    def load_from_file(self) -> None:
        """Load events from the log file into memory.

        Useful for restoring history after restart.
        """
        if not self.log_file or not self.log_file.exists():
            return

        with open(self.log_file) as f:
            for line in f:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    self.events.append(AnvilEvent.from_dict(data))

    def __len__(self) -> int:
        """Return the number of logged events."""
        return len(self.events)
