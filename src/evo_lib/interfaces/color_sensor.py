"""Abstract interface for RGB color sensors."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.peripheral import Placable

if TYPE_CHECKING:
    from evo_lib.task import Task
    from evo_lib.types.color import Color


class ColorSensor(Placable):
    """An RGB color sensor (e.g. TCS34725 behind a TCA9548A mux)."""

    @abstractmethod
    def read_color(self) -> Task[Color]:
        """Read raw RGB values."""

    @abstractmethod
    def calibrate(self, power_color: float, min_color: float, max_color: float) -> None:
        """Calibrate sensor thresholds (LED power, min/max color range)."""
