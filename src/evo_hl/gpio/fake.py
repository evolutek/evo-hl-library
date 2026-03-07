"""GPIO driver — fake implementation for testing without hardware."""

from __future__ import annotations

import logging

from evo_hl.gpio.base import GPIO

log = logging.getLogger(__name__)


class GPIOFake(GPIO):
    """In-memory GPIO for tests and simulation."""

    def __init__(self):
        self.pins: dict[int, dict] = {}

    def init(self) -> None:
        self.pins.clear()
        log.info("GPIO fake initialized")

    def setup_input(self, pin: int) -> None:
        self.pins[pin] = {"output": False, "value": False, "pwm": None}

    def setup_output(self, pin: int, default: bool = False) -> None:
        self.pins[pin] = {"output": True, "value": default, "pwm": None}

    def inject_input(self, pin: int, value: bool) -> None:
        """Inject a value on an input pin for testing."""
        if pin in self.pins and not self.pins[pin]["output"]:
            self.pins[pin]["value"] = value

    def read(self, pin: int) -> bool:
        return self.pins.get(pin, {}).get("value", False)

    def write(self, pin: int, value: bool) -> None:
        if pin in self.pins:
            self.pins[pin]["value"] = value

    def setup_pwm(self, pin: int, frequency: float) -> None:
        self.pins[pin] = {"output": True, "value": False, "pwm": {"freq": frequency, "duty": 0.0}}

    def set_pwm(self, pin: int, duty_cycle: float) -> None:
        if pin in self.pins and self.pins[pin]["pwm"] is not None:
            self.pins[pin]["pwm"]["duty"] = duty_cycle

    def stop_pwm(self, pin: int) -> None:
        if pin in self.pins and self.pins[pin]["pwm"] is not None:
            self.pins[pin]["pwm"] = None

    def close(self) -> None:
        self.pins.clear()
        log.info("GPIO fake closed")
