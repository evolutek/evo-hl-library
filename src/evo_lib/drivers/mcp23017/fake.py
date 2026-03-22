"""MCP23017 driver: fake implementation for testing without hardware."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from evo_lib.component import Component, ComponentHolder
from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIOEdge
from evo_lib.task import ImmediateResultTask

if TYPE_CHECKING:
    from evo_lib.task import Task

log = logging.getLogger(__name__)

NUM_PINS = 16


class MCP23017PinFake(GPIO):
    """In-memory fake for a single MCP23017 pin."""

    def __init__(self, name: str, chip: MCP23017ChipFake, pin: int):
        super().__init__(name)
        self._chip = chip
        self._pin_number = pin
        self._state: bool = False

    def init(self) -> None:
        log.debug("MCP23017 fake pin %d (%s) initialized", self._pin_number, self.name)

    def close(self) -> None:
        pass

    def read(self) -> Task[bool]:
        """Read the in-memory pin state."""
        return ImmediateResultTask(self._state)

    def write(self, state: bool) -> Task[None]:
        """Set the in-memory pin state."""
        self._state = state
        return ImmediateResultTask(None)

    def inject(self, value: bool) -> None:
        """Inject a value for testing (simulates external hardware change)."""
        self._state = value

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        """Not supported on fake MCP23017."""
        raise NotImplementedError(
            "MCP23017 interrupt is not supported in fake driver"
        )


class MCP23017ChipFake(ComponentHolder):
    """In-memory fake for the MCP23017 chip, for tests and simulation."""

    def __init__(self, name: str, address: int = 0x20):
        super().__init__(name)
        self._address = address
        self._pins: dict[int, MCP23017PinFake] = {}

    def init(self) -> None:
        log.info("MCP23017 fake '%s' initialized at 0x%02x", self.name, self._address)

    def close(self) -> None:
        self._pins.clear()
        log.info("MCP23017 fake '%s' closed", self.name)

    def get_subcomponents(self) -> list[Component]:
        """Return all pins that have been created via get_pin."""
        return list(self._pins.values())

    def get_pin(self, pin: int, name: str) -> MCP23017PinFake:
        """Create or retrieve a MCP23017PinFake for the given pin number."""
        if not 0 <= pin < NUM_PINS:
            raise ValueError(f"Pin {pin} out of range (0-{NUM_PINS - 1})")
        if pin in self._pins:
            return self._pins[pin]
        fake_pin = MCP23017PinFake(name, self, pin)
        self._pins[pin] = fake_pin
        return fake_pin
