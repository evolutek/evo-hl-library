"""Composition tests for the Carte Mobile board driver and its virtual twin."""

import pytest

from evo_lib.drivers.board.carte_mobile import CarteMobile, CarteMobileVirtual
from evo_lib.drivers.gpio.mcp23017 import MCP23017Chip
from evo_lib.drivers.gpio.virtual import GPIOChipVirtual
from evo_lib.drivers.i2c.tca9548a import TCA9548A, TCA9548AVirtual
from evo_lib.drivers.i2c.virtual import I2CVirtual
from evo_lib.logger import Logger


@pytest.fixture
def bus():
    b = I2CVirtual()
    b.init()
    b.add_device(0x20)
    b.add_device(0x70)
    yield b
    b.close()


def test_carte_mobile_wires_real_children(bus):
    card = CarteMobile(name="bras_pal", logger=Logger("test"), bus=bus)
    assert isinstance(card.gpio, MCP23017Chip)
    assert isinstance(card.mux, TCA9548A)
    assert card.get_subcomponents() == [card.gpio, card.mux]


def test_carte_mobile_virtual_swaps_every_child():
    bus = I2CVirtual()
    bus.init()
    card = CarteMobileVirtual(name="bras_pal", logger=Logger("test"), bus=bus)
    assert isinstance(card.gpio, GPIOChipVirtual)
    assert isinstance(card.mux, TCA9548AVirtual)
    assert card.get_subcomponents() == [card.gpio, card.mux]
