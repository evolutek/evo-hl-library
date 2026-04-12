"""Tests for I2C virtual and TCA9548A multiplexer."""

import pytest

from evo_lib.drivers.i2c.rpi import RpiI2CVirtual
from evo_lib.drivers.i2c.tca9548a import TCA9548A, TCA9548AVirtual
from evo_lib.drivers.i2c.virtual import I2CVirtual
from evo_lib.logger import Logger


class TestI2CVirtual:
    def test_write_and_read(self):
        bus = I2CVirtual()
        bus.init()
        dev = bus.add_device(0x20)
        dev.inject_read(b"\x42\x43")

        bus.write_to(0x20, b"\x01").wait()
        (result,) = bus.read_from(0x20, 2).wait()

        assert dev.written == [b"\x01"]
        assert result == b"\x42\x43"

    def test_write_then_read(self):
        bus = I2CVirtual()
        bus.init()
        dev = bus.add_device(0x48)
        dev.inject_read(b"\xff")

        (result,) = bus.write_then_read(0x48, b"\x00", 1).wait()

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

        tca = TCA9548A("tca", Logger("test"), bus, address=0x70)
        ch3 = tca.get_channel(3)
        ch3.init()
        (result,) = ch3.read_from(0x29, 1).wait()

        # TCA should have received channel select byte (1 << 3 = 0x08)
        assert tca_dev.written == [bytes([0x08])]
        assert result == b"\xAB"

    def test_channel_out_of_range(self):
        bus = I2CVirtual()
        tca = TCA9548A("tca", Logger("test"), bus, address=0x70)
        with pytest.raises(ValueError):
            tca.get_channel(8)

    def test_scan_excludes_tca_address(self):
        bus = I2CVirtual()
        bus.init()
        bus.add_device(0x70)
        bus.add_device(0x29)

        tca = TCA9548A("tca", Logger("test"), bus, address=0x70)
        ch0 = tca.get_channel(0)
        ch0.init()
        (addresses,) = ch0.scan().wait()
        assert addresses == [0x29]


class TestRpiI2CVirtual:
    """Virtual twin of RpiI2C: same constructor, drop-in replacement."""

    def test_constructor_matches_rpii2c(self):
        # Same (name, logger, bus) signature as RpiI2C
        bus = RpiI2CVirtual("rpi_virt", Logger("test"), bus=1)
        bus.init()
        (addresses,) = bus.scan().wait()
        assert addresses == []

    def test_read_write_delegates_to_inner(self):
        bus = RpiI2CVirtual("rpi_virt", Logger("test"))
        bus.init()
        dev = bus.add_device(0x48)
        dev.inject_read(b"\xAB")
        bus.write_to(0x48, b"\x01").wait()
        assert dev.written == [b"\x01"]
        (result,) = bus.read_from(0x48, 1).wait()
        assert result == b"\xAB"


class TestTCA9548AVirtual:
    """Virtual twin of TCA9548A: inherits real, bypasses mux writes."""

    def test_init_does_not_write_to_bus(self):
        # Parent bus has NO device at 0x70, real TCA would fail. Virtual must not.
        bus = I2CVirtual()
        bus.init()
        tca = TCA9548AVirtual("tca", Logger("test"), bus, address=0x70)
        tca.init()  # should not raise

    def test_channel_select_tracks_state_without_bus_write(self):
        bus = I2CVirtual()
        bus.init()
        # Register downstream device only; no TCA device at 0x70.
        target = bus.add_device(0x29)
        target.inject_read(b"\xEF")

        tca = TCA9548AVirtual("tca", Logger("test"), bus, address=0x70)
        tca.init()
        ch2 = tca.get_channel(2)
        ch2.init()
        (result,) = ch2.read_from(0x29, 1).wait()
        assert result == b"\xEF"
        assert tca._current_channel == 2
