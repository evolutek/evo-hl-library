"""MCP23017 driver — fake implementation for testing without hardware."""

from __future__ import annotations

import logging

from evo_hl.mcp23017.base import MCP23017, NUM_PINS

log = logging.getLogger(__name__)


class MCP23017Fake(MCP23017):
    """In-memory MCP23017 for tests and simulation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pins: dict[int, dict] = {}

    def init(self) -> None:
        self.pins.clear()
        log.info("MCP23017 fake initialized at 0x%02x", self.address)

    def setup_pin(self, pin: int, output: bool, default: bool = False) -> None:
        if not 0 <= pin < NUM_PINS:
            raise ValueError(f"Pin {pin} out of range (0-{NUM_PINS - 1})")
        self.pins[pin] = {"output": output, "value": default if output else False}

    def inject_input(self, pin: int, value: bool) -> None:
        """Inject a value on an input pin for testing."""
        if pin in self.pins and not self.pins[pin]["output"]:
            self.pins[pin]["value"] = value

    def read(self, pin: int) -> bool:
        if pin not in self.pins:
            raise ValueError(f"Pin {pin} not configured — call setup_pin first")
        return self.pins[pin]["value"]

    def write(self, pin: int, value: bool) -> None:
        if pin not in self.pins:
            raise ValueError(f"Pin {pin} not configured — call setup_pin first")
        if not self.pins[pin]["output"]:
            raise ValueError(f"Pin {pin} is configured as input")
        self.pins[pin]["value"] = value

    def close(self) -> None:
        self.pins.clear()
        log.info("MCP23017 fake closed")
