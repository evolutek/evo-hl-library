"""Abstract interface for analog input channels."""

from __future__ import annotations

from abc import abstractmethod

from evo_hl.component import Component


class AnalogInput(Component):
    """A single analog input channel (e.g. ADS1115 channel)."""

    @abstractmethod
    def read_voltage(self) -> float:
        """Read the current voltage (in volts)."""
