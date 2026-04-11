"""Tests for SimpleExecutor."""

import threading

import pytest

from evo_lib.executor import SimpleExecutor


class TestSimpleExecutorExec:
    def test_handle_runs_queued_callback(self):
        executor = SimpleExecutor()
        task = executor.exec(lambda: 42)
        executor.handle()
        assert task.wait() == (42,)


class TestSimpleExecutorError:
    def test_callback_exception_is_propagated_to_task(self):
        executor = SimpleExecutor()
        task = executor.exec(lambda: 1 / 0)
        executor.handle()
        with pytest.raises(ZeroDivisionError):
            task.wait()

    def test_exception_does_not_stop_other_tasks(self):
        executor = SimpleExecutor()
        t1 = executor.exec(lambda: 1 / 0)
        t2 = executor.exec(lambda: 42)
        executor.handle()
        with pytest.raises(ZeroDivisionError):
            t1.wait()
        assert t2.wait() == (42,)


class TestSimpleExecutorRunStop:
    def test_run_processes_tasks_and_stop_exits(self):
        executor = SimpleExecutor()

        t = threading.Thread(target=executor.run)
        t.start()

        task = executor.exec(lambda: 42)
        assert task.wait(timeout=1.0) == (42,)

        executor.stop()
        t.join(timeout=1.0)
        assert not t.is_alive()
