import sched
import time
import traceback
from dataclasses import dataclass
from threading import Event as ThreadEvent
from typing import Callable

from evo_lib.executor import Executor
from evo_lib.logger import Logger


class SchedulerExecutor(Executor):
    def __init__(self, scheduler: "Scheduler", priority: int):
        self.scheduler: "Scheduler" = scheduler
        self.priority: int = priority

    def exec(self, callback: Callable, args: tuple, kwargs: dict[str,]) -> None:
        self.scheduler.schedule_now(self.priority, callback, args, kwargs)


@dataclass(slots = True)
class SchedulerTask:
    callback: Callable
    args: tuple
    kwargs: dict[str,]
    stacktrace: list[traceback.FrameSummary]


class Scheduler:
    def __init__(self, logger: Logger):
        self._py_scheduler = sched.scheduler(time.time, time.sleep)
        self._new_schedule_event = ThreadEvent()
        self._running = False
        self._logger = logger

    def _run_task(self, task: SchedulerTask) -> None:
        try:
            task.callback(*task.args, **task.kwargs)
        except Exception as e:
            caller_stack_trace_msg = ''.join(traceback.format_list(task.stacktrace))
            self._logger.error(f"Error in scheduled task from:\n{caller_stack_trace_msg}")
            called_stack_trace_msg = ''.join(traceback.format_exception(e))
            self._logger.error(f"The error was:\n{called_stack_trace_msg}")

    def schedule_now(
        self, priority: int, callback: Callable, args: tuple = (), kwargs: dict[str,] | None = None
    ) -> sched.Event:
        self._py_scheduler.enter(0, priority, self._run_task, argument=(
            SchedulerTask(callback, args, kwargs or {}, traceback.extract_stack()[:-1]),
        ))
        self._new_schedule_event.set()

    def schedule_after(
        self,
        delay: float,
        priority: int,
        callback: Callable,
        args: tuple = (),
        kwargs: dict[str,] | None = None,
    ) -> sched.Event:
        self._py_scheduler.enter(delay, priority, self._run_task, argument=(
            SchedulerTask(callback, args, kwargs or {}, traceback.extract_stack()[:-1]),
        ))
        self._new_schedule_event.set()

    def schedule_at(
        self,
        timepoint: float,
        priority: int,
        callback: Callable,
        args: tuple = (),
        kwargs: dict[str,] | None = None,
    ) -> sched.Event:
        self._py_scheduler.enterabs(timepoint, priority, self._run_task, argument=(
            SchedulerTask(callback, args, kwargs or {}, traceback.extract_stack()[:-1]),
        ))
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
