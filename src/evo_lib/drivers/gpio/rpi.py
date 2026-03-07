"""GPIO driver: real Raspberry Pi implementation via RPi.GPIO."""

from __future__ import annotations

import logging
import threading
from threading import Thread

from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIOEdge
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)

# Default polling interval for interrupt emulation (seconds)
_POLL_INTERVAL = 0.02


class GPIORpi(GPIO):
    """Native BCM GPIO on Raspberry Pi, one pin per instance."""

    def __init__(self, name: str, pin: int):
        super().__init__(name)
        self._pin = pin
        self._gpio = None  # RPi.GPIO module, imported lazily in init()
        self._stop = threading.Event()
        self._threads: list[Thread] = []

    def init(self) -> None:
        import RPi.GPIO as _RpiGPIO

        _RpiGPIO.setmode(_RpiGPIO.BCM)
        self._gpio = _RpiGPIO
        # Default to input; caller can use write() to switch to output behaviour
        self._gpio.setup(self._pin, self._gpio.IN, pull_up_down=self._gpio.PUD_DOWN)
        log.info("GPIORpi '%s' initialized on pin %d", self._name, self._pin)

    def close(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads.clear()
        if self._gpio is not None:
            self._gpio.cleanup(self._pin)
            log.info("GPIORpi '%s' closed (pin %d)", self._name, self._pin)

    def _check_init(self) -> None:
        if self._gpio is None:
            raise RuntimeError("GPIO not initialized, call init() first")

    def read(self) -> Task[bool]:
        self._check_init()
        value = bool(self._gpio.input(self._pin))
        return ImmediateResultTask(value)

    def write(self, state: bool) -> Task[None]:
        self._check_init()
        self._gpio.setup(self._pin, self._gpio.OUT)
        self._gpio.output(
            self._pin,
            self._gpio.HIGH if state else self._gpio.LOW,
        )
        return ImmediateResultTask(None)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        self._check_init()
        event: Event[bool] = Event()

        def _poll() -> None:
            last = bool(self._gpio.input(self._pin))
            while not self._stop.is_set():
                self._stop.wait(_POLL_INTERVAL)
                current = bool(self._gpio.input(self._pin))
                if current != last:
                    fire = (
                        edge == GPIOEdge.BOTH
                        or (edge == GPIOEdge.RISING and current)
                        or (edge == GPIOEdge.FALLING and not current)
                    )
                    if fire:
                        event.trigger(current)
                last = current

        t = Thread(target=_poll, daemon=True)
        t.start()
        self._threads.append(t)
        return event
