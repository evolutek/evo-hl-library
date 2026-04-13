"""Abstract interface for a serial bus (UART)."""

from abc import abstractmethod

from evo_lib.peripheral import Interface

# Historical Evolutek STM32 default — legacy trajman, recalage, actuator boards
# all run at 38400 baud. Smart-servo buses (AX-12) override via set_baudrate().
DEFAULT_BAUDRATE = 38400
DEFAULT_TIMEOUT = 1.0


class Serial(Interface):
    """A serial bus (UART) abstraction.

    Drivers receive a Serial instead of creating their own serial.Serial.
    This decouples drivers from the transport and enables bus-level simulation.

    Used by: carte-asserv (Pilot), USB2AX (AX-12 SmartServo), RPLidar, etc.
    """

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

    @abstractmethod
    def reset_input_buffer(self) -> None:
        """Discard all bytes currently waiting in the input buffer.

        Used to recover from a desynchronized state after a timeout, or
        to drop the local echo on half-duplex buses (AX-12 Dynamixel)
        before reading a device response.
        """

    def set_baudrate(self, baudrate: int) -> None:
        """Reconfigure the bus baudrate on the fly (no reopen).

        Optional capability. UART-based buses (pyserial, virtual twins)
        override this. Buses with a fixed-speed transport (BT SPP, TCP
        bridges) inherit the default and raise NotImplementedError.

        AX-12 Dynamixel servos rely on this to switch between their
        EEPROM-configured baudrates (1 Mbps, 500 kbps, ...) at runtime.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support runtime baudrate change"
        )

    @property
    @abstractmethod
    def in_waiting(self) -> int:
        """Number of bytes currently available to read."""
