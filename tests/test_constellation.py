"""Composition tests for the Constellation board driver and its virtual twin."""

from evo_lib.drivers.board.constellation import Constellation, ConstellationVirtual
from evo_lib.drivers.i2c.tca9548a import TCA9548A, TCA9548AVirtual
from evo_lib.drivers.i2c.virtual import I2CVirtual
from evo_lib.drivers.pwm.pca9685 import PCA9685Chip, PCA9685ChipVirtual
from evo_lib.logger import Logger


def test_constellation_wires_real_children():
    bus = I2CVirtual()
    bus.init()
    bus.add_device(0x40)
    bus.add_device(0x70)
    card = Constellation(name="face_a", logger=Logger("test"), bus=bus)
    assert isinstance(card.pwm, PCA9685Chip)
    assert isinstance(card.mux, TCA9548A)
    assert card.get_subcomponents() == [card.pwm, card.mux]


def test_constellation_virtual_swaps_every_child():
    bus = I2CVirtual()
    bus.init()
    card = ConstellationVirtual(name="face_a", logger=Logger("test"), bus=bus)
    assert isinstance(card.pwm, PCA9685ChipVirtual)
    assert isinstance(card.mux, TCA9548AVirtual)
    assert card.get_subcomponents() == [card.pwm, card.mux]
