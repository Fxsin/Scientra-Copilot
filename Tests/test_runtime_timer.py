"""Tests for P6.5 runtime_timer."""

import time
import pytest
from scientra.benchmark.runtime_timer import RuntimeTimer, timed, timed_call


class TestRuntimeTimer:
    def test_basic_timing(self):
        t = RuntimeTimer("test")
        t.start()
        time.sleep(0.01)
        t.stop()
        assert t.duration_ms > 0
        assert t.duration_ms < 1000

    def test_duration_before_stop(self):
        t = RuntimeTimer("test")
        t.start()
        time.sleep(0.01)
        # duration should work even before explicit stop
        assert t.duration_ms > 0

    def test_to_metric(self):
        t = RuntimeTimer("my_label")
        t.start()
        time.sleep(0.01)
        t.stop()
        m = t.to_metric()
        assert m.label == "my_label"
        assert m.duration_ms > 0
        assert m.success is True

    def test_warnings(self):
        t = RuntimeTimer("test")
        t.warn("something odd")
        t.warn("another issue")
        m = t.to_metric()
        assert len(m.warnings) == 2

    def test_metadata(self):
        t = RuntimeTimer("test")
        t.add_metadata("count", 42)
        m = t.to_metric()
        assert m.metadata["count"] == 42

    def test_error_capture(self):
        t = RuntimeTimer("test")
        t.start()
        t.stop(success=False, error="Test error")
        m = t.to_metric()
        assert m.success is False
        assert m.error == "Test error"

    def test_unstarted_duration(self):
        t = RuntimeTimer("test")
        assert t.duration_ms == 0.0

    def test_timed_context_manager(self):
        with timed("ctx_test") as t:
            time.sleep(0.01)
        assert t.duration_ms > 0
        assert t.to_metric().success is True

    def test_timed_context_exception(self):
        with pytest.raises(ValueError):
            with timed("ctx_fail") as t:
                raise ValueError("boom")
        assert t.to_metric().success is False
        assert "ValueError" in (t.to_metric().error or "")

    def test_timed_call_success(self):
        def fast_func():
            return 42

        m = timed_call("fast", fast_func)
        assert m.label == "fast"
        assert m.success is True

    def test_timed_call_duration(self):
        def slow_func():
            time.sleep(0.02)

        m = timed_call("slow", slow_func)
        assert m.duration_ms > 10
