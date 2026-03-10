"""Abstract interface for motor controllers (steppers, DC motors, etc.)."""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_hl.component import Component

if TYPE_CHECKING:
    from evo_hl.task import Task


class MotorController(Component):
    """A motor controller that can move to a target position.

    Returns a Task so the caller can track progress or cancel.
    """

    @abstractmethod
    def goto(self, position: int) -> Task[None]:
        """Move to the given position. Returns a Task for tracking/cancellation."""

    @abstractmethod
    def stop(self) -> None:
        """Immediately stop the motor."""
