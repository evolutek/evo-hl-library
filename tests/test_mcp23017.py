"""Tests for MCP23017 GPIO expander (real driver on virtual I2C + virtual chip)."""

import pytest

from evo_lib.drivers.gpio.mcp23017 import MCP23017Chip
from evo_lib.drivers.gpio.virtual import GPIOChipVirtual, GPIOPinVirtual
from evo_lib.drivers.i2c.virtual import I2CBusVirtual
from evo_lib.interfaces.gpio import GPIODirection


@pytest.fixture
def chip():
    c = GPIOChipVirtual(name="test_chip", address=0x20)
    c.init()
    yield c
    c.close()


class TestGPIOChipVirtual:
    def test_get_pin(self, chip):
        pin = chip.get_pin(0, "pin0")
        assert isinstance(pin, GPIOPinVirtual)
        assert pin.name == "pin0"

    def test_get_pin_returns_same_instance(self, chip):
        pin1 = chip.get_pin(3, "pin3")
        pin2 = chip.get_pin(3, "pin3")
        assert pin1 is pin2

    def test_get_pin_bad_number(self, chip):
        with pytest.raises(ValueError):
            chip.get_pin(16, "bad")


class TestMCP23017Chip:
    @pytest.fixture
    def bus_and_chip(self):
        bus = I2CBusVirtual()
        dev = bus.add_device(0x20)
        # init() does two write_then_read (IODIR reads) + two write_to (IODIR writes)
        # Actually init() calls write_register which just does write_to
        chip = MCP23017Chip("test", bus, address=0x20)
        chip.init()
        dev.written.clear()
        return bus, dev, chip

    def test_init_sets_all_inputs(self):
        bus = I2CBusVirtual()
        dev = bus.add_device(0x20)
        chip = MCP23017Chip("test", bus, address=0x20)
        chip.init()
        # init writes 0xFF to IODIR_A (0x00) and IODIR_B (0x01)
        assert dev.written == [bytes([0x00, 0xFF]), bytes([0x01, 0xFF])]

    def test_write_pin(self, bus_and_chip):
        bus, dev, chip = bus_and_chip
        # set_bit reads OLAT then writes it, so inject current register value
        dev.inject_read(b"\x00")  # current OLAT_A = 0
        pin = chip.get_pin(2, "out", direction=GPIODirection.OUTPUT)
        # init: set_bit(IODIR, 2, False) needs a read, set_bit(OLAT, 2, False) needs a read
        dev.inject_read(b"\xff")  # IODIR_A read
        dev.inject_read(b"\x00")  # OLAT_A read
        pin.init()
        dev.written.clear()
        # write True to pin 2 → set_bit(OLAT_A, 2, True)
        dev.inject_read(b"\x00")  # current OLAT_A
        pin.write(True)
        # Should have read OLAT_A register, then written bit 2 set
        assert dev.written == [bytes([0x14]), bytes([0x14, 0x04])]

    def test_read_pin(self, bus_and_chip):
        _, dev, chip = bus_and_chip
        # set_bit for init needs reads
        dev.inject_read(b"\xff")  # IODIR_A read (already input, no change)
        dev.inject_read(b"\x00")  # GPPU_A read
        pin = chip.get_pin(3, "in", direction=GPIODirection.INPUT)
        pin.init()
        dev.written.clear()
        # Inject GPIO_A value with bit 3 set
        dev.inject_read(b"\x08")
        result = pin.read()
        assert result.wait() is True

    def test_pull_up(self, bus_and_chip):
        _, dev, chip = bus_and_chip
        dev.inject_read(b"\xff")  # IODIR_A read
        dev.inject_read(b"\x00")  # GPPU_A read
        pin = chip.get_pin(5, "sensor", direction=GPIODirection.INPUT, pull_up=True)
        pin.init()
        # Last write should be GPPU_A with bit 5 set
        gppu_writes = [w for w in dev.written if w[0] == 0x0C]
        assert gppu_writes[-1] == bytes([0x0C, 0x20])
