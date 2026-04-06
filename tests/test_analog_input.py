"""Tests for ADS1115 analog input drivers."""

import struct

import pytest

from evo_lib.drivers.analog_input.ads1115 import ADS1115Chip
from evo_lib.drivers.analog_input.virtual import AnalogInputChipVirtual, AnalogInputVirtual
from evo_lib.drivers.i2c.virtual import I2CVirtual


class TestAnalogInputVirtual:
    def test_default_voltage_is_zero(self):
        ch = AnalogInputVirtual("ch0")
        ch.init()
        assert ch.read_voltage().wait() == 0.0

    def test_inject_voltage(self):
        ch = AnalogInputVirtual("ch0")
        ch.init()
        ch.inject_voltage(3.3)
        assert ch.read_voltage().wait() == 3.3

    def test_chip_virtual_get_channel(self):
        chip = AnalogInputChipVirtual("adc")
        chip.init()
        ch0 = chip.get_channel(0, "ch0")
        ch1 = chip.get_channel(1, "ch1")
        assert ch0 is not ch1
        assert chip.get_channel(0, "ch0") is ch0
        assert len(chip.get_subcomponents()) == 2

    def test_chip_virtual_bad_channel(self):
        chip = AnalogInputChipVirtual("adc")
        with pytest.raises(ValueError):
            chip.get_channel(4, "bad")


class TestADS1115Chip:
    def test_read_channel_writes_config_and_reads_conversion(self):
        bus = I2CVirtual()
        bus.init()
        dev = bus.add_device(0x48)
        # Inject a raw conversion result: 16384 = 1.024V at ±2.048V FSR
        dev.inject_read(struct.pack(">h", 16384))

        chip = ADS1115Chip("adc", bus, address=0x48, fsr=2.048)
        chip.init()
        ch = chip.get_channel(0, "ch0")
        ch.init()

        voltage = ch.read_voltage().wait()

        # Config register should have been written (3 bytes: reg + 2 config)
        assert len(dev.written) >= 1
        config_write = dev.written[0]
        assert config_write[0] == 0x01  # Config register address
        # Conversion register was read
        assert abs(voltage - 1.024) < 0.001
