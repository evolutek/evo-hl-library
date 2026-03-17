"""Abstract interface for smart servos with position feedback (e.g. Dynamixel AX-12)."""

from __future__ import annotations

from abc import abstractmethod

from evo_lib.component import Component


class SmartServo(Component):
    """A servo with position feedback, speed control, and torque management.

    Unlike a basic Servo (fire-and-forget PWM), a SmartServo reports
    its actual position and can be queried at any time.
    """

    @abstractmethod
    def move(self, position: int) -> None:
        """Move to the given position (native units)."""

    @abstractmethod
    def get_position(self) -> int:
        """Read current position (native units)."""

    @abstractmethod
    def set_speed(self, speed: int) -> None:
        """Set movement speed (native units, 0 = max)."""

    @abstractmethod
    def free(self) -> None:
        """Disable torque (servo goes limp)."""
