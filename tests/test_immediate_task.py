"""Tests for ImmediateResultTask and ImmediateErrorTask."""

import pytest

from evo_lib.task import (
    ImmediateErrorTask,
    ImmediateResultTask,
    TaskCancelledError,
)


class TestImmediateResultTask:
    def test_wait_returns_value(self):
        r = ImmediateResultTask(42)
        assert r.wait() == 42

    def test_is_done(self):
        assert ImmediateResultTask(1).is_done() is True

    def test_on_complete_called_immediately(self):
        received = []
        ImmediateResultTask(42).on_complete(lambda v: received.append(v))
        assert received == [42]

    def test_on_error_not_called(self):
        received = []
        ImmediateResultTask(42).on_error(lambda e: received.append(e))
        assert received == []

    def test_chaining(self):
        received = []
        ImmediateResultTask(1).on_complete(lambda v: received.append(v)).on_error(
            lambda e: received.append(e)
        )
        assert received == [1]

    def test_cancel_then_wait_raises(self):
        task = ImmediateResultTask(42)
        task.cancel()
        with pytest.raises(TaskCancelledError):
            task.wait()

    def test_cancel_then_on_complete_not_called(self):
        received = []
        task = ImmediateResultTask(42)
        task.cancel()
        task.on_complete(lambda v: received.append(v))
        assert received == []


class TestImmediateErrorTask:
    def test_wait_raises(self):
        r = ImmediateErrorTask(ValueError("boom"))
        with pytest.raises(ValueError, match="boom"):
            r.wait()

    def test_is_done(self):
        assert ImmediateErrorTask(ValueError()).is_done() is True

    def test_on_error_called_immediately(self):
        received = []
        ImmediateErrorTask(ValueError("x")).on_error(lambda e: received.append(str(e)))
        assert received == ["x"]

    def test_on_complete_not_called(self):
        received = []
        ImmediateErrorTask(ValueError()).on_complete(lambda v: received.append(v))
        assert received == []
