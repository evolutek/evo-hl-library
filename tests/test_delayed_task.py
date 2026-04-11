"""Tests for Task with progress and cancellation."""

import threading

import pytest

from evo_lib.task import TaskCancelledError, DelayedTask


class TestDelayedTaskComplete:
    def test_complete_and_wait(self):
        task = DelayedTask()
        task.complete(42)
        assert task.wait() == (42,)

    def test_complete_sets_done(self):
        task = DelayedTask()
        assert task.is_done() is False
        task.complete()
        assert task.is_done() is True

    def test_complete_sets_progress_to_1(self):
        task = DelayedTask()
        task.complete()

    def test_on_complete_called(self):
        received = []
        task = DelayedTask()
        task.on_complete(lambda v: received.append(v))
        task.complete(99)
        assert received == [99]

    def test_on_complete_called_if_already_done(self):
        received = []
        task = DelayedTask()
        task.complete(42)
        task.on_complete(lambda v: received.append(v))
        assert received == [42]


class TestDelayedTaskError:
    def test_abort_and_wait_raises(self):
        task = DelayedTask()
        task.error(ValueError("boom"))
        with pytest.raises(ValueError, match="boom"):
            task.wait()

    def test_on_error_called(self):
        received = []
        task = DelayedTask()
        task.on_error(lambda e: received.append(str(e)))
        task.error(ValueError("oops"))
        assert received == ["oops"]

    def test_on_error_called_if_already_done(self):
        received = []
        task = DelayedTask()
        task.error(ValueError("oops"))
        task.on_error(lambda e: received.append(str(e)))
        assert received == ["oops"]

    def test_on_complete_not_called_on_abort(self):
        received = []
        task = DelayedTask()
        task.on_complete(lambda v: received.append(v))
        task.error(ValueError())
        assert received == []


class TestDelayedTaskCancel:
    def test_cancel_calls_handler(self):
        cancelled = []
        task = DelayedTask(on_cancel=lambda: cancelled.append(True))
        task.cancel()
        assert cancelled == [True]

    def test_cancel_aborts_with_cancelled_error(self):
        task = DelayedTask()
        task.cancel()
        with pytest.raises(TaskCancelledError):
            task.wait()

    def test_cancel_without_handler(self):
        task = DelayedTask()
        task.cancel() # Should not raise
        assert task.is_done() is True


class TestDelayedTaskThreaded:
    def test_wait_blocks_until_complete(self):
        task = DelayedTask()
        result = []

        def waiter():
            result.append(task.wait())

        t = threading.Thread(target=waiter)
        t.start()
        task.complete(42)
        t.join(timeout=1.0)
        assert result == [(42,)]

    def test_producer_consumer_pattern(self):
        """Simulate motor goto: producer updates progress, consumer waits."""
        task = DelayedTask(on_cancel=lambda: None)

        def producer():
            task.complete()

        t = threading.Thread(target=producer)
        t.start()
        task.wait()
        t.join(timeout=1.0)
        assert task.is_done() is True
