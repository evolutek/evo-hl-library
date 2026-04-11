import sched
import time
from threading import Event as ThreadEvent
from typing import Callable

from evo_lib.executor import Executor


class SchedulerExecutor(Executor):
    def __init__(self, scheduler: "Scheduler", priority: int):
        self.scheduler: "Scheduler" = scheduler
        self.priority: int = priority

    def exec(self, callback: Callable, args: tuple, kwargs: dict[str,]) -> None:
        self.scheduler.schedule_now(self.priority, callback, args, kwargs)


class Scheduler:
    def __init__(self):
        self._py_scheduler = sched.scheduler(time.time, time.sleep)
        self._new_schedule_event = ThreadEvent()
        self._running = False

    def schedule_now(
        self, priority: int, action: Callable, args: tuple = (), kwargs: dict[str,] | None = None
    ) -> sched.Event:
        self._py_scheduler.enter(0, priority, action, argument=args, kwargs=kwargs or {})
        self._new_schedule_event.set()

    def schedule_after(
        self,
        delay: float,
        priority: int,
        callback: Callable,
        args: tuple = (),
        kwargs: dict[str,] | None = None,
    ) -> sched.Event:
        self._py_scheduler.enter(delay, priority, callback, argument=args, kwargs=kwargs or {})
        self._new_schedule_event.set()

    def schedule_at(
        self,
        timepoint: float,
        priority: int,
        callback: Callable,
        args: tuple = (),
        kwargs: dict[str,] | None = None,
    ) -> sched.Event:
        self._py_scheduler.enterabs(timepoint, priority, callback, argument=args, kwargs=kwargs or {})
        self._new_schedule_event.set()

    def cancel(self, scheduled: sched.Event) -> None:
        self._py_scheduler.cancel(scheduled)

    def run(self) -> None:
        self._running = True
        while self._running:
            self._new_schedule_event.clear()
            self._py_scheduler.run(blocking=True)
            if self._running:
                self._new_schedule_event.wait()

    def stop(self) -> None:
        self._running = False
        self._new_schedule_event.set()

    def handle(self) -> float:
        return self._py_scheduler.run(blocking=False)

    def get_executor(self, priority: int) -> SchedulerExecutor:
        return SchedulerExecutor(self, priority)
