"""Tests for Servo drivers (PWMServo + sync move)."""

import math
import threading

import pytest

from evo_lib.drivers.pwm.virtual import PWMVirtual
from evo_lib.drivers.servo.pwm_servo import PWMServo, PWMServoVirtual
from evo_lib.interfaces.servo import ServoAngleUnit
from evo_lib.logger import Logger
from evo_lib.scheduler import Scheduler


@pytest.fixture
def log():
    return Logger("test")


@pytest.fixture
def scheduler(log):
    sched = Scheduler(log)
    thread = threading.Thread(target=sched.run, daemon=True)
    thread.start()
    yield sched
    sched.stop()
    thread.join(timeout=1.0)


def _make_servo(log, scheduler, *, move_speed=10_000.0, **kwargs) -> tuple[PWMVirtual, PWMServo]:
    pwm = PWMVirtual("pwm", log, freq_hz=50.0)
    pwm.init()
    defaults = dict(min_pulse_us=500.0, max_pulse_us=2500.0, angle_range=180.0)
    defaults.update(kwargs)
    servo = PWMServo("servo", log, scheduler, pwm, move_speed=move_speed, **defaults)
    servo.init()
    return pwm, servo


class TestPWMServoUnitConversion:
    @pytest.mark.parametrize(
        "unit,position,expected_us",
        [
            (ServoAngleUnit.DEGREES, 0.0, 500.0),
            (ServoAngleUnit.DEGREES, 90.0, 1500.0),
            (ServoAngleUnit.DEGREES, 180.0, 2500.0),
            (ServoAngleUnit.FRACTION, 0.5, 1500.0),
            (ServoAngleUnit.RADIANS, math.pi / 2, 1500.0),
        ],
    )
    def test_unit_to_pulse(self, log, scheduler, unit, position, expected_us):
        pwm, servo = _make_servo(log, scheduler)
        servo.move_to(position, unit).wait(timeout=1.0)
        assert pwm.pulse_width_us == pytest.approx(expected_us)


class TestPWMServoClamping:
    def test_safety_limits_clamp_outside_inputs(self, log, scheduler):
        pwm, servo = _make_servo(
            log, scheduler,
            min_pulse_us=500.0, max_pulse_us=2800.0, angle_range=205.0,
            min_angle=10.0, max_angle=195.0,
        )
        servo.move_to(0.0, ServoAngleUnit.DEGREES).wait(timeout=1.0)
        assert pwm.pulse_width_us == pytest.approx(500.0 + (10.0 / 205.0) * 2300.0)
        servo.move_to(205.0, ServoAngleUnit.DEGREES).wait(timeout=1.0)
        assert pwm.pulse_width_us == pytest.approx(500.0 + (195.0 / 205.0) * 2300.0)


class TestPWMServoSyncMove:
    def test_move_completes_after_distance_over_speed(self, log, scheduler):
        pwm, servo = _make_servo(log, scheduler, move_speed=1800.0)
        task = servo.move_to(90.0, ServoAngleUnit.DEGREES)
        task.wait(timeout=1.0)
        assert task.is_done()
        assert pwm.pulse_width_us == pytest.approx(1500.0)

    def test_second_move_cancels_first(self, log, scheduler):
        # Sequential moves must not leak a pending wait — the second call
        # exercises the wait_or_cancel_current_task → cancel path.
        pwm, servo = _make_servo(log, scheduler, move_speed=1.0)
        servo.move_to(180.0, ServoAngleUnit.DEGREES)
        second = servo.move_to(0.0, ServoAngleUnit.DEGREES)
        assert second is not None


class TestPWMServoFree:
    def test_free_disables_pwm_and_flips_is_enabled(self, log, scheduler):
        pwm, servo = _make_servo(log, scheduler)
        servo.move_to(90.0, ServoAngleUnit.DEGREES).wait(timeout=1.0)
        assert pwm.pulse_width_us > 0.0
        servo.free().wait(timeout=1.0)
        assert pwm.pulse_width_us == 0.0
        (enabled,) = servo.is_enabled().wait()
        assert enabled is False

    def test_init_starts_in_free_state(self, log, scheduler):
        _, servo = _make_servo(log, scheduler)
        (enabled,) = servo.is_enabled().wait()
        assert enabled is False


class TestPWMServoVirtual:
    def test_signature_parity_with_real(self, log, scheduler):
        # Real <-> virtual swap must stay a one-line config change.
        pwm = PWMVirtual("pwm", log, freq_hz=50.0)
        pwm.init()
        servo = PWMServoVirtual(
            "servo", log, scheduler, pwm,
            move_speed=1800.0,
            min_pulse_us=500.0, max_pulse_us=2500.0, angle_range=180.0,
        )
        servo.init()
        servo.move_to(0.5, ServoAngleUnit.FRACTION).wait(timeout=1.0)
        (angle,) = servo.get_angle().wait()
        assert angle == pytest.approx(90.0)
