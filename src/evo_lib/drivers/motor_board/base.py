"""Abstract base class for I2C stepper motor controller board."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.component import Component

if TYPE_CHECKING:
    from evo_lib.task import Task


class MotorBoard(Component):
    """Controls stepper motors via a custom I2C motor board.

    This is a low-level driver for the STM32-based stepper controller board,
    not a Pilot implementation. The Pilot layer sits above this and handles
    trajectory planning, coordinate transforms, etc.
    """

    def __init__(self, name: str, address: int = 0x69):
        super().__init__(name)
        self.address = address

    @abstractmethod
    def goto(self, stepper_id: int, steps: int, speed: int) -> Task[bool]:
        """Move stepper to absolute position (steps) at given speed."""

    @abstractmethod
    def move(self, stepper_id: int, steps: int, speed: int) -> Task[bool]:
        """Move stepper by relative steps at given speed."""

    @abstractmethod
    def home(self, stepper_id: int, speed: int) -> Task[bool]:
        """Home the stepper at given speed."""
