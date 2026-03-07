"""GPIO driver — real Raspberry Pi implementation via RPi.GPIO."""

from __future__ import annotations

import logging

from evo_hl.gpio.base import GPIO

log = logging.getLogger(__name__)


class GPIORpi(GPIO):
    """Native BCM GPIO on Raspberry Pi."""

    def __init__(self):
        self._pwms: dict[int, object] = {}

    def init(self) -> None:
        import RPi.GPIO as _RpiGPIO

        _RpiGPIO.setmode(_RpiGPIO.BCM)
        self._gpio = _RpiGPIO
        log.info("RPi GPIO initialized (BCM mode)")

    def setup_input(self, pin: int) -> None:
        self._gpio.setup(pin, self._gpio.IN, pull_up_down=self._gpio.PUD_DOWN)

    def setup_output(self, pin: int, default: bool = False) -> None:
        self._gpio.setup(pin, self._gpio.OUT, initial=self._gpio.HIGH if default else self._gpio.LOW)

    def read(self, pin: int) -> bool:
        return bool(self._gpio.input(pin))

    def write(self, pin: int, value: bool) -> None:
        self._gpio.output(pin, self._gpio.HIGH if value else self._gpio.LOW)

    def setup_pwm(self, pin: int, frequency: float) -> None:
        pwm = self._gpio.PWM(pin, frequency)
        pwm.start(0)
        self._pwms[pin] = pwm

    def set_pwm(self, pin: int, duty_cycle: float) -> None:
        self._pwms[pin].ChangeDutyCycle(duty_cycle)

    def stop_pwm(self, pin: int) -> None:
        if pin in self._pwms:
            self._pwms[pin].stop()
            del self._pwms[pin]

    def close(self) -> None:
        for pwm in self._pwms.values():
            pwm.stop()
        self._pwms.clear()
        self._gpio.cleanup()
        log.info("RPi GPIO closed")
