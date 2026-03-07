"""Abstract base class for TCA9548A I2C multiplexer with TCS34725 color sensors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
NUM_CHANNELS = 8
class Color(Enum):
    """Detected color from TCS34725."""
    Red = "red"
    Green = "green"
    Blue = "blue"
    Unknown = "unknown"
class TCA9548A(ABC):
    """Reads color sensors connected via a TCA9548A I2C multiplexer.

    Each TCA9548A channel (0–7) can have a TCS34725 color sensor.
    The multiplexer selects one channel at a time.
    """

    def __init__(self, address: int = 0x70):
        self.address = address

    @abstractmethod
    def init(self) -> None:
        """Initialize the TCA9548A and probe connected sensors."""

    @abstractmethod
    def read_color(self, channel: int) -> Color:
        """Read color from the sensor on the given TCA channel."""

    @abstractmethod
    def read_rgb(self, channel: int) -> tuple[int, int, int]:
        """Read raw RGB bytes from the sensor on the given TCA channel."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""
