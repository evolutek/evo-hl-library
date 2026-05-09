"""Abstract interface for a CAN bus."""

from abc import abstractmethod
from dataclasses import dataclass

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.event import Event
from evo_lib.peripheral import Interface
from evo_lib.task import Task


@dataclass(slots=True)
class CANMessage:
    heading: int
    data: bytes


@dataclass(slots=True)
class CANFilter:
    id: int
    mask: int


class CAN(Interface):
    commands = DriverCommands()

    @abstractmethod
    @commands.register(
        result=[("extended", ArgTypes.Bool(help="If the CAN bus is using extended IDs"))]
    )
    def is_extended(self) -> bool:
        """Return whether the CAN bus is using extended IDs."""

    @abstractmethod
    def write_sync(self, message: CANMessage) -> None:
        """Send a CAN message synchronously.

        This waits for the message to be sent or correctly queued before returning."""

    @abstractmethod
    def write_async(self, message: CANMessage) -> Task[()]:
        """Send a CAN message asynchronously.

        This returns a Task that completes when the message is sent or correctly queued."""

    @abstractmethod
    def read_sync(self, timeout: float | None = None) -> CANMessage:
        """Read a CAN message synchronously.

        If timeout is None, block indefinitely.
        If timeout is null, do not block, and if there is no message available,
        raise TimeoutError.
        If timeout is not None, raises TimeoutError if the configured timeout
        expires before all bytes are received.
        """

    @abstractmethod
    def read_async(self) -> Event[CANMessage]:
        """Read a message asynchronously (non-blocking).

        Returns None if no message is available.
        """

    @abstractmethod
    def clear_filter(self) -> None:
        """Clear all filters from the CAN bus."""

    @abstractmethod
    def add_filter(self, filter: CANFilter) -> None:
        """Add a filter to the CAN bus."""
