"""MCP23017 driver: Adafruit CircuitPython implementation.

The MCP23017 is a 16-pin I2C GPIO expander. This module exposes it as:
- MCP23017Chip (ComponentHolder): manages I2C connection to the chip
- MCP23017Pin (GPIO): one instance per physical pin
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from evo_lib.component import Component, ComponentHolder
from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIOEdge
from evo_lib.task import ImmediateResultTask

if TYPE_CHECKING:
    from evo_lib.task import Task

# Cached at module level after first lazy import in init()
_Direction = None

log = logging.getLogger(__name__)

NUM_PINS = 16


class MCP23017Pin(GPIO):
    """A single pin on an MCP23017 chip, implementing the GPIO interface."""

    def __init__(self, name: str, chip: MCP23017Chip, pin: int):
        super().__init__(name)
        self._chip = chip
        self._pin_number = pin
        self._hw_pin = None

    def init(self) -> None:
        # The chip handles I2C init, we just grab our hardware pin object
        self._hw_pin = self._chip.get_hw_pin(self._pin_number)
        log.debug("MCP23017 pin %d (%s) initialized", self._pin_number, self.name)

    def close(self) -> None:
        self._hw_pin = None

    def read(self) -> Task[bool]:
        """Read the pin state via the chip's I2C connection."""
        self._hw_pin.direction = _Direction.INPUT
        value = self._hw_pin.value
        return ImmediateResultTask(value)

    def write(self, state: bool) -> Task[None]:
        """Set the pin output state via the chip's I2C connection."""
        self._hw_pin.direction = _Direction.OUTPUT
        self._hw_pin.value = state
        return ImmediateResultTask(None)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        """Not supported on MCP23017 via Adafruit library."""
        raise NotImplementedError(
            "MCP23017 interrupt is not supported by the Adafruit driver"
        )


class MCP23017Chip(ComponentHolder):
    """Manages the I2C connection to one MCP23017 chip.

    Pins are numbered 0-15 (GPA0-GPA7 = 0-7, GPB0-GPB7 = 8-15).
    """

    def __init__(self, name: str, i2c_bus: int, address: int = 0x20):
        super().__init__(name)
        self._i2c_bus = i2c_bus
        self._address = address
        self._mcp = None
        self._pins: dict[int, MCP23017Pin] = {}

    def init(self) -> None:
        """Initialize the I2C connection and the MCP23017 chip."""
        global _Direction

        import board
        import busio
        from adafruit_mcp230xx.mcp23017 import MCP23017 as _HwMCP23017
        from digitalio import Direction

        _Direction = Direction

        # Use the configured I2C bus number to select the correct pins
        scl, sda = self._get_i2c_pins(self._i2c_bus)
        i2c = busio.I2C(scl, sda)
        self._mcp = _HwMCP23017(i2c, address=self._address)
        log.info(
            "MCP23017 '%s' initialized at 0x%02x on bus %d",
            self.name,
            self._address,
            self._i2c_bus,
        )

    def close(self) -> None:
        """Release the I2C connection."""
        self._mcp = None
        self._pins.clear()
        log.info("MCP23017 '%s' closed", self.name)

    def get_subcomponents(self) -> list[Component]:
        """Return all pins that have been created via get_pin."""
        return list(self._pins.values())

    def get_pin(self, pin: int, name: str) -> MCP23017Pin:
        """Create or retrieve a MCP23017Pin for the given pin number."""
        if not 0 <= pin < NUM_PINS:
            raise ValueError(f"Pin {pin} out of range (0-{NUM_PINS - 1})")
        if pin in self._pins:
            return self._pins[pin]
        gpio_pin = MCP23017Pin(name, self, pin)
        self._pins[pin] = gpio_pin
        return gpio_pin

    def get_hw_pin(self, pin: int) -> Any:
        """Return the underlying Adafruit hardware pin object.

        Internal use by MCP23017Pin, not part of the public API.
        """
        if self._mcp is None:
            raise RuntimeError("MCP23017 chip not initialized, call init() first")
        return self._mcp.get_pin(pin)

    @staticmethod
    def _get_i2c_pins(bus: int) -> tuple:
        """Return (SCL, SDA) board pins for the given I2C bus number."""
        import board

        if bus == 1:
            return board.SCL, board.SDA
        # Blinka exposes bus-specific pins as D<n> attributes
        scl_attr = f"SCL{bus}" if hasattr(board, f"SCL{bus}") else None
        sda_attr = f"SDA{bus}" if hasattr(board, f"SDA{bus}") else None
        if scl_attr and sda_attr:
            return getattr(board, scl_attr), getattr(board, sda_attr)
        raise ValueError(
            f"I2C bus {bus} not supported: board has no SCL{bus}/SDA{bus} pins"
        )
