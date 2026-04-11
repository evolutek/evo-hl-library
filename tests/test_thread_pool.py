"""Tests for ThreadPoolExecutor."""

import threading

import pytest

from evo_lib.logger import Logger
from evo_lib.thread_pool import ThreadPoolExecutor


def make_pool(**kwargs) -> ThreadPoolExecutor:
    logger = Logger("test")
    return ThreadPoolExecutor(logger, **kwargs)


class TestThreadPoolExec:
    def test_exec_and_wait(self):
        pool = make_pool()
        task = pool.exec(lambda: 42)
        assert task.wait(timeout=1.0) == (42,)
        pool.stop()


class TestThreadPoolError:
    def test_exception_propagated_to_task(self):
        pool = make_pool()
        task = pool.exec(lambda: 1 / 0)
        with pytest.raises(ZeroDivisionError):
            task.wait(timeout=1.0)
        pool.stop()

    def test_exception_does_not_kill_worker(self):
        pool = make_pool()
        bad = pool.exec(lambda: 1 / 0)
        with pytest.raises(ZeroDivisionError):
            bad.wait(timeout=1.0)
        # Worker should still be alive for the next task
        good = pool.exec(lambda: 42)
        assert good.wait(timeout=1.0) == (42,)
        pool.stop()


class TestThreadPoolWorkers:
    def test_creates_workers_on_demand(self):
        pool = make_pool()
        assert len(pool.workers) == 0
        task = pool.exec(lambda: 1)
        task.wait(timeout=1.0)
        assert len(pool.workers) == 1
        pool.stop()

    def test_max_workers_limits_creation(self):
        pool = make_pool(max_workers=2)
        barrier = threading.Barrier(2, timeout=2.0)
        # Submit 2 blocking tasks to force 2 workers
        t1 = pool.exec(barrier.wait)
        t2 = pool.exec(barrier.wait)
        t1.wait(timeout=2.0)
        t2.wait(timeout=2.0)
        assert len(pool.workers) == 2
        # A third task should not create a new worker
        t3 = pool.exec(lambda: 99)
        assert t3.wait(timeout=1.0) == (99,)
        assert len(pool.workers) == 2
        pool.stop()

    def test_parallel_execution(self):
        pool = make_pool(max_workers=4)
        barrier = threading.Barrier(3, timeout=2.0)
        # 3 tasks that all must reach the barrier to succeed
        tasks = [pool.exec(barrier.wait) for _ in range(3)]
        for task in tasks:
            task.wait(timeout=2.0)
        pool.stop()
