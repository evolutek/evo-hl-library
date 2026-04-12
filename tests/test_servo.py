"""Tests for Servo drivers (PWMServo adapter + virtual)."""

import pytest

from evo_lib.drivers.pwm.virtual import PWMVirtual
from evo_lib.drivers.servo.pwm_servo import PWMServo, PWMServoVirtual
from evo_lib.drivers.servo.virtual import ServoVirtual
from evo_lib.logger import Logger


class TestServoVirtual:
    def test_move_to_angle(self):
        servo = ServoVirtual("test", Logger("test"), angle_range=180.0)
        servo.init()
        servo.move_to_angle(90.0)
        assert servo.current_angle == 90.0
        assert servo.current_fraction == pytest.approx(0.5)

    def test_move_to_fraction(self):
        servo = ServoVirtual("test", Logger("test"), angle_range=180.0)
        servo.init()
        servo.move_to_fraction(0.25)
        assert servo.current_fraction == 0.25
        assert servo.current_angle == pytest.approx(45.0)

    def test_free(self):
        servo = ServoVirtual("test", Logger("test"))
        servo.init()
        assert servo.enabled is True
        servo.free()
        assert servo.enabled is False


class TestPWMServo:
    @pytest.fixture
    def pwm_and_servo(self):
        log = Logger("test")
        pwm = PWMVirtual("pwm", log, freq_hz=50.0)
        pwm.init()
        servo = PWMServo("servo", log, pwm, min_pulse_us=500.0, max_pulse_us=2500.0, angle_range=180.0)
        return pwm, servo

    def test_move_to_angle_center(self, pwm_and_servo):
        pwm, servo = pwm_and_servo
        servo.move_to_angle(90.0)
        assert pwm.pulse_width_us == pytest.approx(1500.0)

    def test_move_to_angle_min(self, pwm_and_servo):
        pwm, servo = pwm_and_servo
        servo.move_to_angle(0.0)
        assert pwm.pulse_width_us == pytest.approx(500.0)

    def test_move_to_angle_max(self, pwm_and_servo):
        pwm, servo = pwm_and_servo
        servo.move_to_angle(180.0)
        assert pwm.pulse_width_us == pytest.approx(2500.0)

    def test_move_to_fraction(self, pwm_and_servo):
        pwm, servo = pwm_and_servo
        servo.move_to_fraction(0.25)
        assert pwm.pulse_width_us == pytest.approx(1000.0)

    def test_free_delegates(self, pwm_and_servo):
        pwm, servo = pwm_and_servo
        pwm.set_duty_cycle(0.5)
        servo.free()
        assert pwm.duty_cycle == 0.0

    def test_angle_clamped(self, pwm_and_servo):
        pwm, servo = pwm_and_servo
        servo.move_to_angle(-10.0)
        assert pwm.pulse_width_us == pytest.approx(500.0)
        servo.move_to_angle(200.0)
        assert pwm.pulse_width_us == pytest.approx(2500.0)

    def test_angle_clamped_by_safety_limits(self):
        log = Logger("test")
        pwm = PWMVirtual("pwm", log, freq_hz=50.0)
        pwm.init()
        servo = PWMServo(
            "s", log, pwm,
            min_pulse_us=500.0, max_pulse_us=2800.0, angle_range=205.0,
            min_angle=10.0, max_angle=195.0,
        )
        # Below safety min → clamped to min_angle=10, pulse ≈ 612.2
        servo.move_to_angle(0.0)
        assert pwm.pulse_width_us == pytest.approx(500.0 + (10.0 / 205.0) * 2300.0)
        # Above safety max → clamped to max_angle=195, pulse ≈ 2687.8
        servo.move_to_angle(205.0)
        assert pwm.pulse_width_us == pytest.approx(500.0 + (195.0 / 205.0) * 2300.0)
        # Within safety range → untouched
        servo.move_to_angle(100.0)
        assert pwm.pulse_width_us == pytest.approx(500.0 + (100.0 / 205.0) * 2300.0)


class TestServoCommands:
    """Exercise DriverCommands registered on the Servo interface + virtual read-backs."""

    def test_move_to_angle_via_command(self):
        servo = ServoVirtual("test", Logger("test"))
        servo.init()
        cmd = ServoVirtual.commands.get("move_to_angle")
        cmd.call(servo, angle=45.0).wait()
        assert servo.current_angle == 45.0

    def test_virtual_commands_include_interface_and_readbacks(self):
        names = {c.name for c in ServoVirtual.commands.get_all()}
        assert names == {
            "move_to_angle", "move_to_fraction", "free",
            "get_angle", "get_fraction", "is_enabled",
        }

    def test_get_angle_via_command(self):
        servo = ServoVirtual("test", Logger("test"))
        servo.init()
        servo.move_to_angle(72.0)
        cmd = ServoVirtual.commands.get("get_angle")
        (angle,) = cmd.call(servo).wait()
        assert angle == 72.0


class TestPWMServoVirtual:
    """Drop-in virtual twin of PWMServo: same signature + read-backs from PWM state."""

    def test_move_propagates_to_pwm(self):
        log = Logger("test")
        pwm = PWMVirtual("pwm", log, freq_hz=50.0)
        pwm.init()
        servo = PWMServoVirtual(
            "servo", log, pwm,
            min_pulse_us=500.0, max_pulse_us=2500.0, angle_range=180.0,
        )
        servo.init()
        servo.move_to_angle(90.0)
        # Center angle -> center pulse (1500us) on the underlying virtual PWM
        assert pwm.pulse_width_us == pytest.approx(1500.0)
        # Read-back derives the angle from the PWM's pulse, not from internal state
        (angle,) = servo.get_angle().wait()
        assert angle == pytest.approx(90.0)

    def test_get_fraction_via_command(self):
        log = Logger("test")
        pwm = PWMVirtual("pwm", log, freq_hz=50.0)
        pwm.init()
        servo = PWMServoVirtual("servo", log, pwm)
        servo.init()
        servo.move_to_fraction(0.25)
        cmd = PWMServoVirtual.commands.get("get_fraction")
        (fraction,) = cmd.call(servo).wait()
        assert fraction == pytest.approx(0.25)
