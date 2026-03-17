"""Abstract interface for angle-controlled servos."""

from __future__ import annotations

from abc import abstractmethod

from evo_lib.component import Component


class Servo(Component):
    """A servo that can move to an angle or be set as a fraction of its range.

    Abstracts away the underlying hardware (PCA9685 channel, direct PWM, etc.).
    """

    @abstractmethod
    def set_angle(self, angle: float) -> None:
        """Move to the given angle (in degrees)."""

    @abstractmethod
    def set_fraction(self, fraction: float) -> None:
        """Set position as a fraction of the full range (0.0 to 1.0)."""

    @abstractmethod
    def free(self) -> None:
        """Disable PWM output (servo goes limp)."""
