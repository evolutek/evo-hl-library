"""Tests for MCP23017 driver using fake implementation."""

import pytest

from evo_lib.drivers.mcp23017.fake import MCP23017ChipFake, MCP23017PinFake


@pytest.fixture
def chip():
    c = MCP23017ChipFake(name="test_chip", address=0x20)
    c.init()
    yield c
    c.close()


class TestMCP23017ChipFake:
    def test_get_pin(self, chip):
        pin = chip.get_pin(0, "pin0")
        assert isinstance(pin, MCP23017PinFake)
        assert pin.name == "pin0"

    def test_get_pin_returns_same_instance(self, chip):
        pin1 = chip.get_pin(3, "pin3")
        pin2 = chip.get_pin(3, "pin3")
        assert pin1 is pin2

    def test_get_pin_bad_number(self, chip):
        with pytest.raises(ValueError):
            chip.get_pin(16, "bad")

    def test_get_subcomponents(self, chip):
        chip.get_pin(0, "a")
        chip.get_pin(5, "b")
        assert len(chip.get_subcomponents()) == 2

    def test_close_clears_pins(self, chip):
        chip.get_pin(0, "pin0")
        chip.close()
        assert len(chip.get_subcomponents()) == 0


class TestMCP23017PinFake:
    def test_read_default(self, chip):
        pin = chip.get_pin(0, "pin0")
        pin.init()
        assert pin.read().wait() is False

    def test_write_then_read(self, chip):
        pin = chip.get_pin(3, "pin3")
        pin.init()
        pin.write(True).wait()
        assert pin.read().wait() is True

    def test_inject(self, chip):
        pin = chip.get_pin(10, "pin10")
        pin.init()
        pin.inject(True)
        assert pin.read().wait() is True

    def test_interrupt_not_supported(self, chip):
        pin = chip.get_pin(0, "pin0")
        pin.init()
        with pytest.raises(NotImplementedError):
            pin.interrupt()
