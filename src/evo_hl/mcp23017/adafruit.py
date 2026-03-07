"""MCP23017 driver — Adafruit CircuitPython implementation."""

from __future__ import annotations

import logging

from evo_hl.mcp23017.base import MCP23017, NUM_PINS

log = logging.getLogger(__name__)


class MCP23017Adafruit(MCP23017):
    """MCP23017 over I2C using Adafruit CircuitPython (any blinka-supported SBC)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mcp = None
        self._pins = {}

    def init(self) -> None:
        import board
        import busio
        from adafruit_mcp230xx.mcp23017 import MCP23017 as _HwMCP23017

        i2c = busio.I2C(board.SCL, board.SDA)
        self._mcp = _HwMCP23017(i2c, address=self.address)
        log.info("MCP23017 initialized at 0x%02x", self.address)

    def setup_pin(self, pin: int, output: bool, default: bool = False) -> None:
        if not 0 <= pin < NUM_PINS:
            raise ValueError(f"Pin {pin} out of range (0-{NUM_PINS - 1})")

        from digitalio import Direction

        mcp_pin = self._mcp.get_pin(pin)
        mcp_pin.direction = Direction.OUTPUT if output else Direction.INPUT
        if output:
            mcp_pin.value = default
        self._pins[pin] = mcp_pin
        log.debug("MCP pin%d → %s", pin, "output" if output else "input")

    def read(self, pin: int) -> bool:
        if pin not in self._pins:
            raise ValueError(f"Pin {pin} not configured — call setup_pin first")
        return self._pins[pin].value

    def write(self, pin: int, value: bool) -> None:
        if pin not in self._pins:
            raise ValueError(f"Pin {pin} not configured — call setup_pin first")
        self._pins[pin].value = value

    def close(self) -> None:
        self._pins.clear()
        self._mcp = None
        log.info("MCP23017 closed")
