"""Base classes for all hardware peripherals."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Peripheral(ABC):
    """
    Lifecycle contract shared by every hardware peripheral.

    Every driver (real or virtual) inherits from this and implements
    ``init`` (acquire resources) and ``close`` (release them).
    """

    def __init__(self, name: str):
        self._name = name

    @property
    def name(self) -> str:
        """Return the name of this peripheral instance."""
        return self._name

    @abstractmethod
    def init(self) -> None:
        """Acquire hardware resources."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""


class Interface(Peripheral):
    """A hardware interface (bus or I/O protocol).

    Subclasses define protocol-specific methods (I2C, Serial, GPIO, etc.).
    """


class InterfaceHolder(Peripheral):
    """A peripheral that manages child peripherals.

    For example, an MCP23017 chip exposes 16 GPIO pins.
    """

    @abstractmethod
    def get_subcomponents(self) -> list[Peripheral]:
        """Return the list of child peripherals managed by this holder."""


class Placable(Peripheral):
    """A peripheral with a physical position on the robot."""
