"""Tests for Task with progress and cancellation."""

import threading

import pytest

from evo_hl.task import CancelledError, Task


class TestTaskComplete:
    def test_complete_and_wait(self):
        task = Task()
        task.complete(42)
        assert task.wait() == 42

    def test_complete_sets_done(self):
        task = Task()
        assert task.is_done() is False
        task.complete()
        assert task.is_done() is True

    def test_complete_sets_progress_to_1(self):
        task = Task()
        task.complete()
        assert task.progress == 1.0

    def test_on_complete_called(self):
        received = []
        task = Task()
        task.on_complete(lambda v: received.append(v))
        task.complete(99)
        assert received == [99]

    def test_on_complete_called_if_already_done(self):
        received = []
        task = Task()
        task.complete(42)
        task.on_complete(lambda v: received.append(v))
        assert received == [42]


class TestTaskAbort:
    def test_abort_and_wait_raises(self):
        task = Task()
        task.abort(ValueError("boom"))
        with pytest.raises(ValueError, match="boom"):
            task.wait()

    def test_on_error_called(self):
        received = []
        task = Task()
        task.on_error(lambda e: received.append(str(e)))
        task.abort(ValueError("oops"))
        assert received == ["oops"]

    def test_on_error_called_if_already_done(self):
        received = []
        task = Task()
        task.abort(ValueError("oops"))
        task.on_error(lambda e: received.append(str(e)))
        assert received == ["oops"]

    def test_on_complete_not_called_on_abort(self):
        received = []
        task = Task()
        task.on_complete(lambda v: received.append(v))
        task.abort(ValueError())
        assert received == []


class TestTaskCancel:
    def test_cancel_calls_handler(self):
        cancelled = []
        task = Task(on_cancel=lambda: cancelled.append(True))
        task.cancel()
        assert cancelled == [True]

    def test_cancel_aborts_with_cancelled_error(self):
        task = Task()
        task.cancel()
        with pytest.raises(CancelledError):
            task.wait()

    def test_cancel_without_handler(self):
        task = Task()
        task.cancel()  # should not raise
        assert task.is_done() is True


class TestTaskProgress:
    def test_progress_default_zero(self):
        assert Task().progress == 0.0

    def test_set_progress(self):
        task = Task()
        task.progress = 0.5
        assert task.progress == 0.5


class TestTaskThreaded:
    def test_wait_blocks_until_complete(self):
        task = Task()
        result = []

        def waiter():
            result.append(task.wait())

        t = threading.Thread(target=waiter)
        t.start()
        task.complete(42)
        t.join(timeout=1.0)
        assert result == [42]

    def test_producer_consumer_pattern(self):
        """Simulate motor goto: producer updates progress, consumer waits."""
        task = Task(on_cancel=lambda: None)
        progress_log = []

        def producer():
            for i in range(1, 5):
                task.progress = i / 4
                progress_log.append(task.progress)
            task.complete()

        t = threading.Thread(target=producer)
        t.start()
        task.wait()
        t.join(timeout=1.0)
        assert progress_log == [0.25, 0.5, 0.75, 1.0]
        assert task.is_done() is True
