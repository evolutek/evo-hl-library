"""SICK TIM driver — fake implementation for testing."""

from __future__ import annotations

import logging
from typing import Callable

from evo_hl.tim.base import Tim

log = logging.getLogger(__name__)


class TimFake(Tim):
    """In-memory TIM for tests and simulation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.robots: list[tuple[float, float]] = []
        self.scanning = False

    def init(self) -> None:
        log.info("TIM fake initialized (%s:%d)", self.ip, self.port)

    def inject_robots(self, robots: list[tuple[float, float]]) -> None:
        """Inject detected robot positions for testing."""
        self.robots = robots

    def start_scanning(self, callback: Callable | None = None) -> None:
        self.scanning = True

    def stop_scanning(self) -> None:
        self.scanning = False

    def get_robots(self) -> list[tuple[float, float]]:
        return list(self.robots)

    def close(self) -> None:
        self.scanning = False
        self.robots.clear()
        log.info("TIM fake closed")
