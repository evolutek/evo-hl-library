"""Graph runner: binds a graph to a scheduler and runs nodes."""

from evo_lib.logger import Logger
from evo_lib.scheduler import Scheduler


class GraphRunner:
    def __init__(self, logger: Logger, scheduler: Scheduler):
        self._scheduler = scheduler
        self._logger = logger

    def get_logger(self) -> Logger:
        return self._logger

    def get_scheduler(self) -> Scheduler:
        return self._scheduler
