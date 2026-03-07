"""Abstract interface for an I2C bus."""

from abc import ABC, abstractmethod


class I2CBus(ABC):
    """A single I2C bus (real, virtual, or a TCA9548A mux channel).

    Drivers receive an I2CBus instead of creating their own busio.I2C.
    This decouples drivers from the transport and enables bus-level simulation.
    """

    @abstractmethod
    def write_to(self, address: int, data: bytes) -> None:
        """Write raw bytes to a device at the given 7-bit address."""

    @abstractmethod
    def read_from(self, address: int, count: int) -> bytes:
        """Read count bytes from a device at the given 7-bit address."""

    @abstractmethod
    def write_then_read(self, address: int, out_data: bytes, in_count: int) -> bytes:
        """Write out_data then immediately read in_count bytes (repeated start).

        This is the most common I2C pattern: send a register address,
        then read back its value without releasing the bus.
        """

    @abstractmethod
    def scan(self) -> list[int]:
        """Return the list of 7-bit addresses that ACK on the bus."""
