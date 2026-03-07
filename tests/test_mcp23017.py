"""Tests for GPIOChipFake (MCP23017-like GPIO expander simulation)."""

import pytest

from evo_lib.drivers.gpio.fake import GPIOPinFake, GPIOChipFake


@pytest.fixture
def chip():
    c = GPIOChipFake(name="test_chip", address=0x20)
    c.init()
    yield c
    c.close()


class TestGPIOChipFake:
    def test_get_pin(self, chip):
        pin = chip.get_pin(0, "pin0")
        assert isinstance(pin, GPIOPinFake)
        assert pin.name == "pin0"

    def test_get_pin_returns_same_instance(self, chip):
        pin1 = chip.get_pin(3, "pin3")
        pin2 = chip.get_pin(3, "pin3")
        assert pin1 is pin2

    def test_get_pin_bad_number(self, chip):
        with pytest.raises(ValueError):
            chip.get_pin(16, "bad")
