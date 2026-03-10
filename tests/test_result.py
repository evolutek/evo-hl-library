"""Tests for Result, InstantResult, ErrorResult, DelayedResult, TaskRunner."""

import time

import pytest

from evo_hl.result import (
    DelayedResult,
    ErrorResult,
    InstantResult,
    TaskRunner,
)


class TestInstantResult:
    def test_wait_returns_value(self):
        r = InstantResult(42)
        assert r.wait() == 42

    def test_wait_default_none(self):
        r = InstantResult()
        assert r.wait() is None

    def test_is_done(self):
        assert InstantResult(1).is_done() is True

    def test_on_complete_called_immediately(self):
        received = []
        InstantResult(42).on_complete(lambda v: received.append(v))
        assert received == [42]

    def test_on_error_not_called(self):
        received = []
        InstantResult(42).on_error(lambda e: received.append(e))
        assert received == []

    def test_chaining(self):
        received = []
        InstantResult(1).on_complete(lambda v: received.append(v)).on_error(
            lambda e: received.append(e)
        )
        assert received == [1]


class TestErrorResult:
    def test_wait_raises(self):
        r = ErrorResult(ValueError("boom"))
        with pytest.raises(ValueError, match="boom"):
            r.wait()

    def test_is_done(self):
        assert ErrorResult(ValueError()).is_done() is True

    def test_on_error_called_immediately(self):
        received = []
        ErrorResult(ValueError("x")).on_error(lambda e: received.append(str(e)))
        assert received == ["x"]

    def test_on_complete_not_called(self):
        received = []
        ErrorResult(ValueError()).on_complete(lambda v: received.append(v))
        assert received == []


class TestDelayedResult:
    def test_wait_returns_value(self):
        runner = TaskRunner(max_workers=1)
        r = runner.run(lambda: 42)
        assert isinstance(r, DelayedResult)
        assert r.wait() == 42
        runner.stop()

    def test_wait_raises_on_error(self):
        def fail():
            raise RuntimeError("oops")

        runner = TaskRunner(max_workers=1)
        r = runner.run(fail)
        with pytest.raises(RuntimeError, match="oops"):
            r.wait()
        runner.stop()

    def test_is_done_eventually(self):
        runner = TaskRunner(max_workers=1)
        r = runner.run(lambda: 1)
        r.wait()
        assert r.is_done() is True
        runner.stop()

    def test_on_complete_callback(self):
        received = []
        runner = TaskRunner(max_workers=1)
        r = runner.run(lambda: 99)
        r.on_complete(lambda v: received.append(v))
        r.wait()
        time.sleep(0.05)  # let callback fire
        assert received == [99]
        runner.stop()

    def test_on_error_callback(self):
        received = []

        def fail():
            raise ValueError("bad")

        runner = TaskRunner(max_workers=1)
        r = runner.run(fail)
        r.on_error(lambda e: received.append(str(e)))
        try:
            r.wait()
        except ValueError:
            pass
        time.sleep(0.05)
        assert received == ["bad"]
        runner.stop()

    def test_future_property(self):
        runner = TaskRunner(max_workers=1)
        r = runner.run(lambda: 1)
        assert r.future is not None
        r.wait()
        runner.stop()


class TestTaskRunner:
    def test_multiple_tasks(self):
        runner = TaskRunner(max_workers=2)
        r1 = runner.run(lambda: 1)
        r2 = runner.run(lambda: 2)
        assert r1.wait() == 1
        assert r2.wait() == 2
        runner.stop()

    def test_blocking_task(self):
        runner = TaskRunner(max_workers=1)
        r = runner.run(time.sleep, 0.1)
        assert r.is_done() is False
        r.wait()
        assert r.is_done() is True
        runner.stop()
