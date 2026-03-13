"""Abstract interface for smart servos with position feedback (e.g. Dynamixel AX-12)."""

from abc import abstractmethod

from evo_lib.interfaces.servo import Servo

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from evo_lib.task import Task


class SmartServo(Servo):
    """A servo with position feedback, speed control, and torque management.

    Unlike a basic Servo (fire-and-forget PWM), a SmartServo reports
    its actual position and can be queried at any time.
    """

    @abstractmethod
    def move_to_position(self, position: int) -> Task[None]:
        """Move to the given position (native units)."""

    @abstractmethod
    def get_position(self) -> Task[int]:
        """Read current position (in native units)."""

    @abstractmethod
    def get_angle(self) -> Task[float]:
        """Read current position (in degrees)."""

    @abstractmethod
    def get_fraction(self) -> Task[float]:
        """Read current position (as a fraction between 0 and 1)."""

    @abstractmethod
    def set_speed(self, speed: float) -> Task[None]:
        """Set movement speed (as a fraction between 0 and 1)."""

    # @abstractmethod
    # def get_stress(self) -> Task[float]:
    #     """Get stress on servo."""
