"""Factory functions for MCP23017 driver instantiation from config."""

from __future__ import annotations

from evo_lib.drivers.mcp23017.config import MCP23017Config
from evo_lib.drivers.mcp23017.adafruit import MCP23017Chip, MCP23017Pin
from evo_lib.drivers.mcp23017.fake import MCP23017ChipFake, MCP23017PinFake
from evo_lib.interfaces.gpio import GPIO


def create_mcp23017(
    config: MCP23017Config, *, fake: bool = False,
) -> tuple[MCP23017Chip | MCP23017ChipFake, dict[int, GPIO]]:
    """Create an MCP23017 chip and its pins from config.

    Returns:
        A tuple of (chip, pins_dict) where pins_dict maps pin number to GPIO.
    """
    if fake:
        chip = MCP23017ChipFake(name=config.name, address=config.address)
    else:
        chip = MCP23017Chip(
            name=config.name, i2c_bus=config.i2c_bus, address=config.address,
        )

    pins: dict[int, GPIO] = {}
    for pin_number, pin_name in config.pins.items():
        pins[pin_number] = chip.get_pin(pin_number, pin_name)

    return chip, pins
