"""Abstract interface for an I2C bus."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.peripheral import Interface

if TYPE_CHECKING:
    from evo_lib.task import Task


class I2C(Interface):
    """A single I2C bus (real, virtual, or a TCA9548A mux channel).

    Drivers receive an I2C instead of creating their own busio.I2C.
    This decouples drivers from the transport and enables bus-level simulation.

    All methods return Task so the interface stays consistent with the rest
    of the library (GPIO, PWM, Servo, ...) and can be exposed via
    DriverCommands to the REPL. Real implementations wrap synchronous busio
    calls in ImmediateResultTask, so there is no added latency.
    """

    commands = DriverCommands()

    @abstractmethod
    @commands.register(
        args=[
            ("address", ArgTypes.U8(help="7-bit I2C device address")),
            ("data", ArgTypes.Bytes()),
        ],
        result=[],
    )
    def write_to(self, address: int, data: bytes) -> Task[()]:
        """Write raw bytes to a device at the given 7-bit address."""

    @abstractmethod
    @commands.register(
        args=[
            ("address", ArgTypes.U8(help="7-bit I2C device address")),
            ("count", ArgTypes.U16(help="Number of bytes to read")),
        ],
        result=[("data", ArgTypes.Bytes())],
    )
    def read_from(self, address: int, count: int) -> Task[bytes]:
        """Read count bytes from a device at the given 7-bit address."""

    @abstractmethod
    @commands.register(
        args=[
            ("address", ArgTypes.U8(help="7-bit I2C device address")),
            ("out_data", ArgTypes.Bytes()),
            ("in_count", ArgTypes.U16(help="Number of bytes to read after the write")),
        ],
        result=[("data", ArgTypes.Bytes())],
    )
    def write_then_read(self, address: int, out_data: bytes, in_count: int) -> Task[bytes]:
        """Write out_data then immediately read in_count bytes (repeated start).

        This is the most common I2C pattern: send a register address,
        then read back its value without releasing the bus.
        """

    @abstractmethod
    @commands.register(
        args=[],
        result=[("addresses", ArgTypes.Array(ArgTypes.U8()))],
    )
    def scan(self) -> Task[list[int]]:
        """Return the list of 7-bit addresses that ACK on the bus."""
