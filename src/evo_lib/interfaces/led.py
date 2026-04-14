"""Abstract interface for a single intensity-controlled LED."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.peripheral import Placable

if TYPE_CHECKING:
    from evo_lib.task import Task


class LED(Placable):
    """A single LED whose brightness is driven as a fraction in 0.0-1.0.

    Implementations typically wrap a PWM channel (LED on a PCA9685 output,
    on an RPi PWM pin, ...) but the interface stays transport-agnostic.
    """

    commands = DriverCommands()

    @abstractmethod
    @commands.register(
        args=[("intensity", ArgTypes.F32(help="Brightness fraction (0.0 = off, 1.0 = full)"))],
        result=[],
    )
    def set_intensity(self, intensity: float) -> Task[()]:
        """Set the LED brightness; values outside 0.0-1.0 are clamped."""

    @abstractmethod
    @commands.register(
        args=[],
        result=[("intensity", ArgTypes.F32(help="Last commanded intensity (0.0-1.0)"))],
    )
    def get_intensity(self) -> Task[float]:
        """Return the last commanded brightness."""
