"""Abstract base class for ADS1115 4-channel 16-bit ADC."""

from __future__ import annotations

from abc import ABC, abstractmethod
NUM_CHANNELS = 4
class ADS1115(ABC):
    """Reads analog voltages from an ADS1115 I2C ADC (4 single-ended channels)."""

    def __init__(self, address: int = 0x48):
        self.address = address

    @abstractmethod
    def init(self) -> None:
        """Initialize the ADC hardware."""

    @abstractmethod
    def read_voltage(self, channel: int) -> float:
        """Read voltage on a channel (0–3). Returns volts."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""
