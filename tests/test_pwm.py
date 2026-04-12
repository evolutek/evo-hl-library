"""Tests for PWM drivers (PCA9685 on virtual I2C + virtual chip + RPi sysfs + ESC)."""

import pytest

from evo_lib.drivers.i2c.virtual import I2CVirtual
from evo_lib.drivers.pwm.pca9685 import PCA9685Chip, PCA9685ChipVirtual
from evo_lib.drivers.pwm.rpi import RpiPWM, RpiPWMVirtual
from evo_lib.drivers.pwm.virtual import PWMChipVirtual, PWMVirtual
from evo_lib.logger import Logger


class TestPWMVirtual:
    def test_set_duty_cycle(self):
        pwm = PWMVirtual("test", Logger("test"), freq_hz=50.0)
        pwm.init()
        pwm.set_duty_cycle(0.5)
        assert pwm.duty_cycle == 0.5
        # At 50Hz, period = 20000us, 50% = 10000us
        assert pwm.pulse_width_us == pytest.approx(10000.0)

    def test_set_pulse_width_us(self):
        pwm = PWMVirtual("test", Logger("test"), freq_hz=50.0)
        pwm.init()
        pwm.set_pulse_width_us(1500.0)
        assert pwm.pulse_width_us == pytest.approx(1500.0)
        assert pwm.duty_cycle == pytest.approx(0.075)

    def test_free(self):
        pwm = PWMVirtual("test", Logger("test"))
        pwm.init()
        pwm.set_duty_cycle(0.5)
        pwm.free()
        assert pwm.duty_cycle == 0.0

    def test_clamp(self):
        pwm = PWMVirtual("test", Logger("test"))
        pwm.init()
        pwm.set_duty_cycle(1.5)
        assert pwm.duty_cycle == 1.0
        pwm.set_duty_cycle(-0.5)
        assert pwm.duty_cycle == 0.0


class TestPWMChipVirtual:
    def test_get_channel(self):
        chip = PWMChipVirtual("test", Logger("test"))
        ch = chip.get_channel(0, "ch0")
        assert isinstance(ch, PWMVirtual)
        assert ch.name == "ch0"

    def test_get_channel_returns_same_instance(self):
        chip = PWMChipVirtual("test", Logger("test"))
        ch1 = chip.get_channel(3, "ch3")
        ch2 = chip.get_channel(3, "ch3")
        assert ch1 is ch2

    def test_get_channel_bad_number(self):
        chip = PWMChipVirtual("test", Logger("test"))
        with pytest.raises(ValueError):
            chip.get_channel(16, "bad")


class TestPCA9685Chip:
    @pytest.fixture
    def bus_and_chip(self):
        bus = I2CVirtual()
        bus.init()
        dev = bus.add_device(0x40)
        # init() reads MODE1 then does several writes
        dev.inject_read(b"\x00")  # MODE1 read
        chip = PCA9685Chip("test", Logger("test"), bus, address=0x40, freq_hz=50.0)
        chip.init()
        dev.written.clear()
        return bus, dev, chip

    def test_init_prescale(self):
        bus = I2CVirtual()
        bus.init()
        dev = bus.add_device(0x40)
        dev.inject_read(b"\x00")  # MODE1 read
        chip = PCA9685Chip("test", Logger("test"), bus, address=0x40, freq_hz=50.0)
        chip.init()
        # Expected sequence:
        # [0] MODE1 read addr, [1] MODE1 sleep+clear restart, [2] PRESCALE,
        # [3] MODE1 wake+AI, [4] ALL_LED_OFF broadcast (warm-reset safety),
        # [5] MODE1 wake+AI+restart
        assert dev.written[0] == bytes([0x00])  # MODE1 read addr
        assert dev.written[1] == bytes([0x00, 0x10])  # sleep mode
        assert dev.written[2] == bytes([0xFE, 121])  # prescale
        assert dev.written[3] == bytes([0x00, 0x20])  # wake + AI
        assert dev.written[4] == bytes([0xFA, 0, 0, 0, 0x10])  # ALL_LED full-off
        assert dev.written[5] == bytes([0x00, 0xA0])  # restart + AI

    def test_set_duty_cycle_half(self, bus_and_chip):
        _, dev, chip = bus_and_chip
        ch = chip.get_channel(0, "ch0")
        ch.set_duty_cycle(0.5)
        # off_count = round(0.5 * 4096) = 2048
        # write: base_reg=0x06, on_l=0, on_h=0, off_l=0x00, off_h=0x08
        assert dev.written[-1] == bytes([0x06, 0, 0, 0x00, 0x08])

    def test_set_duty_cycle_full_off(self, bus_and_chip):
        _, dev, chip = bus_and_chip
        ch = chip.get_channel(0, "ch0")
        ch.set_duty_cycle(0.0)
        # Full off: off_h has bit 4 set
        assert dev.written[-1] == bytes([0x06, 0, 0, 0, 0x10])

    def test_set_duty_cycle_full_on(self, bus_and_chip):
        _, dev, chip = bus_and_chip
        ch = chip.get_channel(0, "ch0")
        ch.set_duty_cycle(1.0)
        # Full on: on_h has bit 4 set
        assert dev.written[-1] == bytes([0x06, 0, 0x10, 0, 0])

    def test_set_pulse_width_us(self, bus_and_chip):
        _, dev, chip = bus_and_chip
        ch = chip.get_channel(0, "ch0")
        ch.set_pulse_width_us(1500.0)
        # duty = 1500 / 20000 = 0.075, off_count = round(0.075 * 4096) = 307
        # 307 = 0x133 -> off_l=0x33, off_h=0x01
        assert dev.written[-1] == bytes([0x06, 0, 0, 0x33, 0x01])

    def test_channel_2_register_offset(self, bus_and_chip):
        _, dev, chip = bus_and_chip
        ch = chip.get_channel(2, "ch2")
        ch.set_duty_cycle(0.0)
        # Channel 2 base = 0x06 + 4*2 = 0x0E
        assert dev.written[-1][0] == 0x0E

    def test_channel_out_of_range(self, bus_and_chip):
        _, _, chip = bus_and_chip
        with pytest.raises(ValueError):
            chip.get_channel(16, "bad")


class TestRpiPWM:
    @pytest.fixture
    def sysfs_pwm(self, tmp_path):
        """Create a fake sysfs PWM tree."""
        chip = tmp_path / "pwmchip0"
        chip.mkdir()
        (chip / "export").write_text("")
        pwm0 = chip / "pwm0"
        pwm0.mkdir()
        for f in ("period", "duty_cycle", "enable"):
            (pwm0 / f).write_text("0")
        return RpiPWM("test", Logger("test"), channel=0, freq_hz=50.0, chip_path=str(chip))

    def test_init_sets_period(self, sysfs_pwm, tmp_path):
        sysfs_pwm.init()
        period = (tmp_path / "pwmchip0" / "pwm0" / "period").read_text()
        assert period == "20000000"  # 50Hz = 20ms = 20_000_000ns

    def test_set_duty_cycle(self, sysfs_pwm, tmp_path):
        sysfs_pwm.init()
        sysfs_pwm.set_duty_cycle(0.5)
        duty = (tmp_path / "pwmchip0" / "pwm0" / "duty_cycle").read_text()
        assert duty == "10000000"  # 50% of 20ms

    def test_set_pulse_width_us(self, sysfs_pwm, tmp_path):
        sysfs_pwm.init()
        sysfs_pwm.set_pulse_width_us(1500.0)
        duty = (tmp_path / "pwmchip0" / "pwm0" / "duty_cycle").read_text()
        assert duty == "1500000"  # 1500us = 1_500_000ns

    def test_free(self, sysfs_pwm, tmp_path):
        sysfs_pwm.init()
        sysfs_pwm.set_duty_cycle(0.5)
        sysfs_pwm.free()
        duty = (tmp_path / "pwmchip0" / "pwm0" / "duty_cycle").read_text()
        assert duty == "0"

    def test_invalid_channel(self):
        with pytest.raises(ValueError):
            RpiPWM("bad", Logger("test"), channel=2)


class TestPCA9685ChipVirtual:
    """Drop-in virtual twin of PCA9685Chip: zero-setup, no I2C writes."""

    def test_constructor_matches_real_signature(self):
        # Same (name, logger, bus, address, freq_hz) as PCA9685Chip
        bus = I2CVirtual()
        bus.init()
        chip = PCA9685ChipVirtual("pca_virt", Logger("test"), bus, address=0x40, freq_hz=50.0)
        chip.init()  # must not write to bus (no device at 0x40)

    def test_channel_is_driveable_without_i2c_setup(self):
        bus = I2CVirtual()
        bus.init()
        chip = PCA9685ChipVirtual("pca_virt", Logger("test"), bus)
        chip.init()
        ch = chip.get_channel(2, "ch2")
        ch.set_duty_cycle(0.5)
        assert ch.duty_cycle == 0.5


class TestRpiPWMVirtual:
    """Drop-in virtual twin of RpiPWM: same sysfs-style signature, no I/O."""

    def test_constructor_matches_rpipwm_signature(self):
        pwm = RpiPWMVirtual("rpi_pwm_virt", Logger("test"), channel=0, freq_hz=50.0)
        pwm.init()
        pwm.set_duty_cycle(0.5)
        assert pwm.duty_cycle == 0.5

    def test_invalid_channel_rejected_like_real(self):
        with pytest.raises(ValueError):
            RpiPWMVirtual("bad", Logger("test"), channel=2)
