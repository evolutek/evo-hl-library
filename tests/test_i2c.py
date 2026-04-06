"""Tests for I2C virtual and TCA9548A multiplexer."""

import pytest

from evo_lib.drivers.i2c.tca9548a import TCA9548A
from evo_lib.drivers.i2c.virtual import I2CVirtual


class TestI2CVirtual:
    def test_write_and_read(self):
        bus = I2CVirtual()
        bus.init()
        dev = bus.add_device(0x20)
        dev.inject_read(b"\x42\x43")

        bus.write_to(0x20, b"\x01")
        result = bus.read_from(0x20, 2)

        assert dev.written == [b"\x01"]
        assert result == b"\x42\x43"

    def test_write_then_read(self):
        bus = I2CVirtual()
        bus.init()
        dev = bus.add_device(0x48)
        dev.inject_read(b"\xff")

        result = bus.write_then_read(0x48, b"\x00", 1)

        assert dev.written == [b"\x00"]
        assert result == b"\xff"

    def test_unregistered_address_raises(self):
        bus = I2CVirtual()
        bus.init()
        with pytest.raises(OSError):
            bus.write_to(0x99, b"\x00")

    def test_read_buffer_underflow_raises(self):
        bus = I2CVirtual()
        bus.init()
        bus.add_device(0x20)
        with pytest.raises(OSError):
            bus.read_from(0x20, 1)


class TestTCA9548A:
    def test_channel_selection(self):
        bus = I2CVirtual()
        bus.init()
        tca_dev = bus.add_device(0x70)
        target_dev = bus.add_device(0x29)
        target_dev.inject_read(b"\xAB")

        tca = TCA9548A("tca", bus, address=0x70)
        ch3 = tca.get_channel(3)
        ch3.init()
        result = ch3.read_from(0x29, 1)

        # TCA should have received channel select byte (1 << 3 = 0x08)
        assert tca_dev.written == [bytes([0x08])]
        assert result == b"\xAB"

    def test_channel_out_of_range(self):
        bus = I2CVirtual()
        tca = TCA9548A("tca", bus, address=0x70)
        with pytest.raises(ValueError):
            tca.get_channel(8)

    def test_scan_excludes_tca_address(self):
        bus = I2CVirtual()
        bus.init()
        bus.add_device(0x70)
        bus.add_device(0x29)

        tca = TCA9548A("tca", bus, address=0x70)
        ch0 = tca.get_channel(0)
        ch0.init()
        assert ch0.scan() == [0x29]
