"""Unified runtime timer for P6.5 benchmark.

No external performance libraries required.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

from scientra.benchmark.benchmark_schema import RuntimeMetric


class RuntimeTimer:
    """Simple wall-clock timer with warning capture."""

    def __init__(self, label: str) -> None:
        self.label = label
        self._start_ns: int = 0
        self._end_ns: int = 0
        self._success: bool = True
        self._error: str | None = None
        self._warnings: list[str] = []
        self._metadata: dict[str, Any] = {}

    def start(self) -> RuntimeTimer:
        self._start_ns = time.perf_counter_ns()
        return self

    def stop(self, success: bool = True, error: str | None = None) -> RuntimeTimer:
        self._end_ns = time.perf_counter_ns()
        self._success = success
        self._error = error
        return self

    def warn(self, message: str) -> None:
        self._warnings.append(message)

    def add_metadata(self, key: str, value: Any) -> None:
        self._metadata[key] = value

    @property
    def duration_ms(self) -> float:
        if self._start_ns == 0:
            return 0.0
        end = self._end_ns if self._end_ns > 0 else time.perf_counter_ns()
        return (end - self._start_ns) / 1_000_000.0

    def to_metric(self) -> RuntimeMetric:
        return RuntimeMetric(
            label=self.label,
            duration_ms=round(self.duration_ms, 3),
            success=self._success,
            error=self._error,
            warnings=list(self._warnings),
            metadata=dict(self._metadata),
        )


@contextmanager
def timed(label: str) -> Any:
    """Context manager for timing a block of code.

    Usage:
        with timed("my_operation") as timer:
            do_work()
        print(timer.duration_ms)
    """
    t = RuntimeTimer(label)
    t.start()
    try:
        yield t
        t.stop(success=True)
    except Exception as exc:
        t.stop(success=False, error=f"{type(exc).__name__}: {exc}")
        raise


def timed_call(label: str, func: Any, *args: Any, **kwargs: Any) -> RuntimeMetric:
    """Time a single function call and return a RuntimeMetric."""
    t = RuntimeTimer(label)
    t.start()
    try:
        func(*args, **kwargs)
        t.stop(success=True)
    except Exception as exc:
        t.stop(success=False, error=f"{type(exc).__name__}: {exc}")
    return t.to_metric()


def timed_call_return(label: str, func: Any, *args: Any, **kwargs: Any) -> tuple[Any, RuntimeMetric]:
    """Time a function call and return (result, RuntimeMetric)."""
    t = RuntimeTimer(label)
    t.start()
    result = None
    try:
        result = func(*args, **kwargs)
        t.stop(success=True)
    except Exception as exc:
        t.stop(success=False, error=f"{type(exc).__name__}: {exc}")
        raise
    return result, t.to_metric()
