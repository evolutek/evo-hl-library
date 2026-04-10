import sched
import time
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
        self.s = sched.scheduler(time.time, time.sleep)

    def schedule_now(
        self, priority: int, action: Callable, args: tuple = (), kwargs: dict[str,] = {}
    ) -> sched.Event:
        self.s.enter(0, priority, action, argument=args, kwargs=kwargs)

    def schedule_after(
        self,
        delay: float,
        priority: int,
        callback: Callable,
        args: tuple = (),
        kwargs: dict[str,] = {},
    ) -> sched.Event:
        self.s.enter(delay, priority, callback, argument=args, kwargs=kwargs)

    def schedule_at(
        self,
        timepoint: float,
        priority: int,
        callback: Callable,
        args: tuple = (),
        kwargs: dict[str,] = {},
    ) -> sched.Event:
        self.s.enterabs(timepoint, priority, callback, argument=args, kwargs=kwargs)

    def cancel(self, scheduled: sched.Event) -> None:
        self.s.cancel(scheduled)

    def run(self) -> None:
        self.s.run(blocking=True)

    def handle(self) -> float:
        return self.s.run(blocking=False)

    def get_executor(self, priority: int) -> SchedulerExecutor:
        return SchedulerExecutor(self, priority)
