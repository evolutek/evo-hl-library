"""Abstract interface for a serial bus (UART)."""

from abc import ABC, abstractmethod


class SerialBus(ABC):
    """A serial bus (UART) abstraction.

    Drivers receive a SerialBus instead of creating their own serial.Serial.
    This decouples drivers from the transport and enables bus-level simulation.

    Used by: carte-asserv (Pilot), USB2AX (AX-12 SmartServo), RPLidar, etc.
    """

    @abstractmethod
    def open(self) -> None:
        """Open the serial port. Must be called before any read/write."""

    @abstractmethod
    def close(self) -> None:
        """Close the serial port and release the underlying resource."""

    @abstractmethod
    def write(self, data: bytes) -> None:
        """Write raw bytes to the serial port."""

    @abstractmethod
    def read(self, count: int) -> bytes:
        """Read exactly count bytes (blocking until all received or timeout).

        Raises TimeoutError if the configured timeout expires before
        all bytes are received.
        """

    @abstractmethod
    def read_available(self) -> bytes:
        """Read all bytes currently available without blocking.

        Returns an empty bytes object if nothing is available.
        """

    @abstractmethod
    def flush(self) -> None:
        """Flush the output buffer (wait until all bytes are sent)."""

    @property
    @abstractmethod
    def in_waiting(self) -> int:
        """Number of bytes currently available to read."""
