"""Tests for TCS34725 color sensor drivers."""

import struct

from evo_lib.drivers.color_sensor.tcs34725 import TCS34725
from evo_lib.drivers.color_sensor.virtual import ColorSensorVirtual
from evo_lib.drivers.i2c.virtual import I2CVirtual
from evo_lib.types.color import Color


class TestColorSensorVirtual:
    def test_default_is_black(self):
        sensor = ColorSensorVirtual("cs0")
        sensor.init()
        color = sensor.read_color().wait()
        assert color.r == 0.0 and color.g == 0.0 and color.b == 0.0

    def test_inject_color(self):
        sensor = ColorSensorVirtual("cs0")
        sensor.init()
        sensor.inject_color(Color(1.0, 0.5, 0.0))
        color = sensor.read_color().wait()
        assert color.r == 1.0
        assert color.g == 0.5
        assert color.b == 0.0

    def test_calibrate(self):
        sensor = ColorSensorVirtual("cs0")
        sensor.calibrate(0.8, 10.0, 200.0)
        assert sensor._power_color == 0.8


class TestTCS34725:
    def test_init_enables_sensor(self):
        bus = I2CVirtual()
        bus.init()
        dev = bus.add_device(0x29)
        # Inject dummy reads for init (not used, but needed if any reads occur)

        sensor = TCS34725("cs0", bus, address=0x29)
        sensor.init()

        # Should have written to ENABLE register (0x80 | 0x00 = 0x80)
        assert len(dev.written) >= 2
        # First write: PON
        assert dev.written[0][0] == 0x80
        assert dev.written[0][1] == 0x01

    def test_read_color_parses_rgbc(self):
        bus = I2CVirtual()
        bus.init()
        dev = bus.add_device(0x29)

        sensor = TCS34725("cs0", bus, address=0x29)
        sensor.init()

        # Inject RGBC data: C=1000, R=500, G=250, B=100 (little-endian 16-bit)
        dev.inject_read(struct.pack("<HHHH", 1000, 500, 250, 100))

        color = sensor.read_color().wait()
        assert abs(color.r - 0.5) < 0.01
        assert abs(color.g - 0.25) < 0.01
        assert abs(color.b - 0.1) < 0.01
