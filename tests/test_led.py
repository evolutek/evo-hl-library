"""Tests for PWMLed (LED interface wrapping a PWM channel)."""

import pytest

from evo_lib.drivers.led.pwm_led import PWMLed
from evo_lib.drivers.pwm.virtual import PWMVirtual
from evo_lib.logger import Logger


@pytest.fixture
def led():
    logger = Logger("test")
    pwm = PWMVirtual(name="pwm", logger=logger)
    pwm.init().wait()
    led = PWMLed(name="led", logger=logger, pwm=pwm)
    led.init().wait()
    return led, pwm


class TestPWMLed:
    def test_set_intensity_drives_duty_cycle(self, led):
        led_obj, pwm = led
        led_obj.set_intensity(0.3).wait()
        assert abs(pwm.duty_cycle - 0.3) < 1e-6

    def test_set_intensity_clamps(self, led):
        led_obj, pwm = led
        led_obj.set_intensity(1.5).wait()
        assert pwm.duty_cycle == 1.0
        led_obj.set_intensity(-0.5).wait()
        assert pwm.duty_cycle == 0.0

    def test_get_intensity_returns_last_commanded(self, led):
        led_obj, _ = led
        led_obj.set_intensity(0.42).wait()
        (v,) = led_obj.get_intensity().wait()
        assert abs(v - 0.42) < 1e-6
