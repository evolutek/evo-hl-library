"""GPIO driver: real Raspberry Pi implementation via RPi.GPIO."""

from __future__ import annotations

import logging
import threading
from threading import Thread

from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIOEdge
from evo_lib.task import ImmediateErrorTask, ImmediateResultTask, Task

log = logging.getLogger(__name__)

INPUT = "input"
OUTPUT = "output"

# Default polling interval for interrupt emulation (seconds)
_POLL_INTERVAL = 0.02


class GPIORpi(GPIO):
    """Native BCM GPIO on Raspberry Pi, one pin per instance."""

    def __init__(self, name: str, pin: int, direction: str = INPUT):
        super().__init__(name)
        self._pin = pin
        self._direction = direction
        self._gpio = None
        self._stop = threading.Event()
        self._threads: list[Thread] = []

    def init(self) -> None:
        import RPi.GPIO as _RpiGPIO

        current = _RpiGPIO.getmode()
        if current is None or current == -1:
            _RpiGPIO.setmode(_RpiGPIO.BCM)
        elif current != _RpiGPIO.BCM:
            raise RuntimeError(
                f"RPi.GPIO mode already set to {current}, expected BCM ({_RpiGPIO.BCM})"
            )
        self._gpio = _RpiGPIO
        if self._direction == INPUT:
            self._gpio.setup(self._pin, self._gpio.IN, pull_up_down=self._gpio.PUD_DOWN)
        else:
            self._gpio.setup(self._pin, self._gpio.OUT, initial=self._gpio.LOW)
        log.info("GPIORpi '%s' initialized on pin %d (%s)", self._name, self._pin, self._direction)

    def close(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads.clear()
        if self._gpio is not None:
            self._gpio.cleanup(self._pin)

    def _check_init(self) -> None:
        if self._gpio is None:
            raise RuntimeError("GPIO not initialized, call init() first")

    def read(self) -> Task[bool]:
        self._check_init()
        if self._direction != INPUT:
            return ImmediateErrorTask(NotImplementedError("read() requires INPUT direction"))
        return ImmediateResultTask(bool(self._gpio.input(self._pin)))

    def write(self, state: bool) -> Task[None]:
        self._check_init()
        if self._direction != OUTPUT:
            return ImmediateErrorTask(NotImplementedError("write() requires OUTPUT direction"))
        self._gpio.output(self._pin, self._gpio.HIGH if state else self._gpio.LOW)
        return ImmediateResultTask(None)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        self._check_init()
        if self._direction != INPUT:
            raise NotImplementedError("interrupt() requires INPUT direction")
        event: Event[bool] = Event()

        def _poll(edge: GPIOEdge = edge) -> None:
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
