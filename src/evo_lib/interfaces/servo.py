"""Abstract interface for angle-controlled servos."""

from abc import abstractmethod

from evo_lib.component import Component

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from evo_lib.task import Task


class Servo(Component):
    """A servo that can move to an angle or be set as a fraction of its range.

    Abstracts away the underlying hardware (PCA9685 channel, direct PWM, etc.).
    """

    @abstractmethod
    def move_to_angle(self, angle: float) -> Task[None]:
        """Move to the given angle (in degrees)."""

    @abstractmethod
    def move_to_fraction(self, fraction: float) -> Task[None]:
        """Set position as a fraction of the full range (0.0 to 1.0)."""

    @abstractmethod
    def free(self) -> Task[None]:
        """Disable PWM output (servo goes limp)."""
