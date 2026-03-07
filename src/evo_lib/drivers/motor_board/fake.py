"""I2C motor board driver, fake implementation for testing."""

from __future__ import annotations

import logging

from evo_lib.drivers.motor_board.base import MotorBoard
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)


class MotorBoardFake(MotorBoard):
    """In-memory stepper motor board for tests and simulation."""

    def __init__(self, name: str = "motor_board_fake", **kwargs):
        super().__init__(name, **kwargs)
        self.steppers: dict[int, dict] = {}

    def init(self) -> None:
        self.steppers.clear()
        log.info("Motor board fake initialized at 0x%02x", self.address)

    def _ensure(self, stepper_id: int) -> dict:
        if stepper_id not in self.steppers:
            self.steppers[stepper_id] = {"position": 0, "speed": 0}
        return self.steppers[stepper_id]

    def goto(self, stepper_id: int, steps: int, speed: int) -> Task[bool]:
        s = self._ensure(stepper_id)
        s["position"] = steps
        s["speed"] = speed
        return ImmediateResultTask(True)

    def move(self, stepper_id: int, steps: int, speed: int) -> Task[bool]:
        s = self._ensure(stepper_id)
        s["position"] += steps
        s["speed"] = speed
        return ImmediateResultTask(True)

    def home(self, stepper_id: int, speed: int) -> Task[bool]:
        s = self._ensure(stepper_id)
        s["position"] = 0
        s["speed"] = speed
        return ImmediateResultTask(True)

    def close(self) -> None:
        self.steppers.clear()
        log.info("Motor board fake closed")
