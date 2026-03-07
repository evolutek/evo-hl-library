"""Abstract base class for MCP23017 16-pin I2C GPIO expander."""

from __future__ import annotations

from abc import ABC, abstractmethod
NUM_PINS = 16
class MCP23017(ABC):
    """Controls digital I/O via an MCP23017 I2C GPIO expander.

    Pins are numbered 0–15 (GPA0–GPA7 = 0–7, GPB0–GPB7 = 8–15).
    """

    def __init__(self, address: int = 0x20):
        self.address = address

    @abstractmethod
    def init(self) -> None:
        """Initialize the MCP23017 hardware."""

    @abstractmethod
    def setup_pin(self, pin: int, output: bool, default: bool = False) -> None:
        """Configure a pin as input (output=False) or output (output=True)."""

    @abstractmethod
    def read(self, pin: int) -> bool:
        """Read pin state. Works for both input and output pins."""

    @abstractmethod
    def write(self, pin: int, value: bool) -> None:
        """Set output pin state. Raises if pin is configured as input."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""
