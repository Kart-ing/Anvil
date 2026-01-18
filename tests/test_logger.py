"""Tests for Anvil logging and observability."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from anvil import Anvil, AnvilEvent, AnvilLogger, EventType


@pytest.fixture
def temp_tools_dir():
    """Create a temporary directory for tool files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "anvil_tools"


@pytest.fixture
def temp_log_file():
    """Create a temporary log file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        yield Path(f.name)


@pytest.fixture
def anvil(temp_tools_dir):
    """Create an Anvil instance with temporary directory (using stub generator)."""
    return Anvil(tools_dir=temp_tools_dir, use_stub=True)


@pytest.fixture
def anvil_with_log(temp_tools_dir, temp_log_file):
    """Create an Anvil instance with logging enabled."""
    return Anvil(tools_dir=temp_tools_dir, use_stub=True, log_file=temp_log_file)


class TestAnvilEvent:
    def test_create_event(self):
        """Create an AnvilEvent with required fields."""
        now = datetime.now()
        event = AnvilEvent(
            timestamp=now,
            event_type=EventType.TOOL_EXECUTED,
            tool_name="test_tool",
        )

        assert event.timestamp == now
        assert event.event_type == EventType.TOOL_EXECUTED
        assert event.tool_name == "test_tool"
        assert event.duration_ms is None
        assert event.error is None
        assert event.metadata == {}

    def test_create_event_with_all_fields(self):
        """Create an AnvilEvent with all fields."""
        now = datetime.now()
        event = AnvilEvent(
            timestamp=now,
            event_type=EventType.TOOL_FAILED,
            tool_name="failing_tool",
            duration_ms=150.5,
            error="Something went wrong",
            metadata={"attempt": 1, "args": ["x", "y"]},
        )

        assert event.duration_ms == 150.5
        assert event.error == "Something went wrong"
        assert event.metadata == {"attempt": 1, "args": ["x", "y"]}

    def test_to_dict(self):
        """Event converts to dictionary correctly."""
        now = datetime.now()
        event = AnvilEvent(
            timestamp=now,
            event_type=EventType.TOOL_GENERATED,
            tool_name="new_tool",
            duration_ms=500.0,
            metadata={"version": "1.0"},
        )

        data = event.to_dict()

        assert data["timestamp"] == now.isoformat()
        assert data["event_type"] == "tool_generated"
        assert data["tool_name"] == "new_tool"
        assert data["duration_ms"] == 500.0
        assert data["metadata"] == {"version": "1.0"}

    def test_from_dict(self):
        """Event can be reconstructed from dictionary."""
        now = datetime.now()
        data = {
            "timestamp": now.isoformat(),
            "event_type": "tool_healed",
            "tool_name": "healed_tool",
            "duration_ms": 200.0,
            "error": None,
            "metadata": {"attempt": 2},
        }

        event = AnvilEvent.from_dict(data)

        assert event.timestamp == now
        assert event.event_type == EventType.TOOL_HEALED
        assert event.tool_name == "healed_tool"
        assert event.duration_ms == 200.0
        assert event.metadata == {"attempt": 2}


class TestAnvilLogger:
    def test_log_event(self):
        """Logger stores events."""
        logger = AnvilLogger()
        event = AnvilEvent(
            timestamp=datetime.now(),
            event_type=EventType.TOOL_EXECUTED,
            tool_name="logged_tool",
        )

        logger.log(event)

        assert len(logger) == 1
        assert logger.events[0] is event

    def test_log_multiple_events(self):
        """Logger stores multiple events."""
        logger = AnvilLogger()

        for i in range(5):
            logger.log(
                AnvilEvent(
                    timestamp=datetime.now(),
                    event_type=EventType.TOOL_EXECUTED,
                    tool_name=f"tool_{i}",
                )
            )

        assert len(logger) == 5

    def test_clear(self):
        """Logger can be cleared."""
        logger = AnvilLogger()
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_EXECUTED,
                tool_name="tool",
            )
        )

        logger.clear()

        assert len(logger) == 0


class TestLoggerGetHistory:
    def test_get_all_history(self):
        """get_history returns all events."""
        logger = AnvilLogger()
        for i in range(3):
            logger.log(
                AnvilEvent(
                    timestamp=datetime.now(),
                    event_type=EventType.TOOL_EXECUTED,
                    tool_name=f"tool_{i}",
                )
            )

        history = logger.get_history()

        assert len(history) == 3

    def test_filter_by_tool_name(self):
        """get_history filters by tool name."""
        logger = AnvilLogger()
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_EXECUTED,
                tool_name="tool_a",
            )
        )
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_EXECUTED,
                tool_name="tool_b",
            )
        )
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_EXECUTED,
                tool_name="tool_a",
            )
        )

        history = logger.get_history(tool_name="tool_a")

        assert len(history) == 2
        assert all(e.tool_name == "tool_a" for e in history)

    def test_filter_by_event_type(self):
        """get_history filters by event type."""
        logger = AnvilLogger()
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_EXECUTED,
                tool_name="tool",
            )
        )
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_FAILED,
                tool_name="tool",
            )
        )
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_EXECUTED,
                tool_name="tool",
            )
        )

        history = logger.get_history(event_type=EventType.TOOL_FAILED)

        assert len(history) == 1
        assert history[0].event_type == EventType.TOOL_FAILED

    def test_filter_by_since(self):
        """get_history filters by timestamp."""
        logger = AnvilLogger()
        old_time = datetime.now() - timedelta(hours=2)
        recent_time = datetime.now()

        logger.log(
            AnvilEvent(
                timestamp=old_time,
                event_type=EventType.TOOL_EXECUTED,
                tool_name="old_tool",
            )
        )
        logger.log(
            AnvilEvent(
                timestamp=recent_time,
                event_type=EventType.TOOL_EXECUTED,
                tool_name="recent_tool",
            )
        )

        history = logger.get_history(since=datetime.now() - timedelta(hours=1))

        assert len(history) == 1
        assert history[0].tool_name == "recent_tool"

    def test_limit_results(self):
        """get_history respects limit."""
        logger = AnvilLogger()
        for i in range(10):
            logger.log(
                AnvilEvent(
                    timestamp=datetime.now(),
                    event_type=EventType.TOOL_EXECUTED,
                    tool_name=f"tool_{i}",
                )
            )

        history = logger.get_history(limit=3)

        assert len(history) == 3

    def test_results_sorted_newest_first(self):
        """get_history returns newest first."""
        logger = AnvilLogger()
        times = [datetime.now() + timedelta(seconds=i) for i in range(3)]

        for i, t in enumerate(times):
            logger.log(
                AnvilEvent(
                    timestamp=t,
                    event_type=EventType.TOOL_EXECUTED,
                    tool_name=f"tool_{i}",
                )
            )

        history = logger.get_history()

        assert history[0].timestamp >= history[1].timestamp >= history[2].timestamp


class TestLoggerGetStats:
    def test_get_stats_empty(self):
        """get_stats for tool with no events."""
        logger = AnvilLogger()

        stats = logger.get_stats("nonexistent")

        assert stats["tool_name"] == "nonexistent"
        assert stats["total_executions"] == 0
        assert stats["successful"] == 0
        assert stats["failed"] == 0
        assert stats["success_rate"] == 0.0

    def test_get_stats_with_executions(self):
        """get_stats counts successful executions."""
        logger = AnvilLogger()
        for _ in range(5):
            logger.log(
                AnvilEvent(
                    timestamp=datetime.now(),
                    event_type=EventType.TOOL_EXECUTED,
                    tool_name="my_tool",
                    duration_ms=100.0,
                )
            )

        stats = logger.get_stats("my_tool")

        assert stats["total_executions"] == 5
        assert stats["successful"] == 5
        assert stats["failed"] == 0
        assert stats["success_rate"] == 1.0
        assert stats["avg_duration_ms"] == 100.0

    def test_get_stats_with_failures(self):
        """get_stats counts failures."""
        logger = AnvilLogger()
        # 3 successes
        for _ in range(3):
            logger.log(
                AnvilEvent(
                    timestamp=datetime.now(),
                    event_type=EventType.TOOL_EXECUTED,
                    tool_name="flaky",
                    duration_ms=50.0,
                )
            )
        # 2 failures
        for _ in range(2):
            logger.log(
                AnvilEvent(
                    timestamp=datetime.now(),
                    event_type=EventType.TOOL_FAILED,
                    tool_name="flaky",
                    error="Random error",
                )
            )

        stats = logger.get_stats("flaky")

        assert stats["total_executions"] == 5
        assert stats["successful"] == 3
        assert stats["failed"] == 2
        assert stats["success_rate"] == 0.6

    def test_get_stats_with_heals(self):
        """get_stats counts heal attempts."""
        logger = AnvilLogger()
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_FAILED,
                tool_name="broken",
            )
        )
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_HEALED,
                tool_name="broken",
            )
        )
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_EXECUTED,
                tool_name="broken",
            )
        )

        stats = logger.get_stats("broken")

        assert stats["healed"] == 1

    def test_get_stats_duration_stats(self):
        """get_stats calculates duration statistics."""
        logger = AnvilLogger()
        durations = [100.0, 200.0, 300.0]
        for d in durations:
            logger.log(
                AnvilEvent(
                    timestamp=datetime.now(),
                    event_type=EventType.TOOL_EXECUTED,
                    tool_name="timed",
                    duration_ms=d,
                )
            )

        stats = logger.get_stats("timed")

        assert stats["avg_duration_ms"] == 200.0
        assert stats["min_duration_ms"] == 100.0
        assert stats["max_duration_ms"] == 300.0


class TestLoggerGetRecentErrors:
    def test_get_recent_errors(self):
        """get_recent_errors returns failed events."""
        logger = AnvilLogger()
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_EXECUTED,
                tool_name="ok",
            )
        )
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_FAILED,
                tool_name="bad",
                error="Error 1",
            )
        )
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_FAILED,
                tool_name="worse",
                error="Error 2",
            )
        )

        errors = logger.get_recent_errors()

        assert len(errors) == 2
        assert all(e.event_type == EventType.TOOL_FAILED for e in errors)


class TestLoggerFileIO:
    def test_writes_to_file(self, temp_log_file):
        """Logger writes events to file."""
        logger = AnvilLogger(log_file=temp_log_file)
        logger.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_EXECUTED,
                tool_name="file_tool",
                duration_ms=100.0,
            )
        )

        # Check file contents
        content = temp_log_file.read_text()
        assert "file_tool" in content
        assert "tool_executed" in content

    def test_writes_json_lines(self, temp_log_file):
        """Logger writes valid JSON lines format."""
        logger = AnvilLogger(log_file=temp_log_file)
        for i in range(3):
            logger.log(
                AnvilEvent(
                    timestamp=datetime.now(),
                    event_type=EventType.TOOL_EXECUTED,
                    tool_name=f"tool_{i}",
                )
            )

        # Parse each line as JSON
        lines = temp_log_file.read_text().strip().split("\n")
        assert len(lines) == 3

        for line in lines:
            data = json.loads(line)
            assert "timestamp" in data
            assert "event_type" in data
            assert "tool_name" in data

    def test_load_from_file(self, temp_log_file):
        """Logger can load events from file."""
        # Write some events
        logger1 = AnvilLogger(log_file=temp_log_file)
        logger1.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_EXECUTED,
                tool_name="restored_tool",
            )
        )
        logger1.log(
            AnvilEvent(
                timestamp=datetime.now(),
                event_type=EventType.TOOL_FAILED,
                tool_name="restored_tool",
                error="Some error",
            )
        )

        # Create new logger and load from file
        logger2 = AnvilLogger(log_file=temp_log_file)
        logger2.load_from_file()

        assert len(logger2) == 2
        assert logger2.events[0].tool_name == "restored_tool"


class TestAnvilLoggingIntegration:
    def test_tool_execution_logged(self, anvil):
        """Tool execution is logged."""
        tool = anvil.use_tool(name="logged_exec", intent="Test logging")
        tool.run(x=1)

        events = anvil.logger.get_history(tool_name="logged_exec")

        # Should have generation + execution events
        assert len(events) >= 1
        exec_events = [e for e in events if e.event_type == EventType.TOOL_EXECUTED]
        assert len(exec_events) == 1
        assert exec_events[0].duration_ms is not None

    def test_tool_generation_logged(self, anvil):
        """Tool generation is logged."""
        anvil.use_tool(name="logged_gen", intent="Test generation logging")

        events = anvil.logger.get_history(tool_name="logged_gen")
        gen_events = [e for e in events if e.event_type == EventType.TOOL_GENERATED]

        assert len(gen_events) == 1
        assert gen_events[0].metadata.get("version") == "1.0"

    def test_tool_failure_logged(self, anvil, temp_tools_dir):
        """Tool failure is logged."""
        tool = anvil.use_tool(name="logged_fail", intent="Test failure logging")

        # Break the tool
        tool_path = temp_tools_dir / "logged_fail.py"
        tool_path.write_text("def run(**kwargs): raise ValueError('Logged error')")
        anvil._loader.clear_cache("logged_fail")
        anvil.self_healing = False

        try:
            tool.run(x=1)
        except RuntimeError:
            pass

        events = anvil.logger.get_history(tool_name="logged_fail")
        fail_events = [e for e in events if e.event_type == EventType.TOOL_FAILED]

        assert len(fail_events) == 1
        assert "Logged error" in fail_events[0].error

    def test_logger_property(self, anvil):
        """Anvil.logger property returns the logger."""
        logger = anvil.logger

        assert isinstance(logger, AnvilLogger)
        assert logger is anvil._logger

    def test_get_stats_through_anvil(self, anvil):
        """Can get stats through anvil.logger."""
        tool = anvil.use_tool(name="stats_tool", intent="Test stats")
        tool.run(a=1)
        tool.run(b=2)
        tool.run(c=3)

        stats = anvil.logger.get_stats("stats_tool")

        assert stats["successful"] == 3

    def test_log_file_integration(self, anvil_with_log, temp_log_file):
        """Anvil writes logs to file when configured."""
        tool = anvil_with_log.use_tool(name="file_logged", intent="Test file logging")
        tool.run(data="test")

        content = temp_log_file.read_text()
        assert "file_logged" in content
        assert "tool_executed" in content
