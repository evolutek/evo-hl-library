"""Abstract interface for analog input channels."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.peripheral import Placable

if TYPE_CHECKING:
    from evo_lib.task import Task


class AnalogInput(Placable):
    """A single analog input channel (e.g. ADS1115 channel)."""

    @abstractmethod
    def read_voltage(self) -> Task[float]:
        """Read the current voltage (in volts)."""
