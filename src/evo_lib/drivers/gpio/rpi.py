"""GPIO driver: real Raspberry Pi implementation via gpiod (libgpiod v2)."""

import logging
import threading
from datetime import timedelta
from threading import Thread

from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIODirection, GPIOEdge
from evo_lib.task import ImmediateErrorTask, ImmediateResultTask, Task

log = logging.getLogger(__name__)

# Default chip path (gpiochip0 on Pi 3/4, gpiochip4 on Pi 5)
DEFAULT_CHIP = "/dev/gpiochip0"


class GPIORpi(GPIO):
    """Native BCM GPIO on Raspberry Pi via gpiod, one pin per instance."""

    def __init__(
        self,
        name: str,
        pin: int,
        direction: GPIODirection = GPIODirection.INPUT,
        chip: str = DEFAULT_CHIP,
    ):
        super().__init__(name)
        self._pin = pin
        self._direction = direction
        self._chip = chip
        self._request = None
        self._stop = threading.Event()
        self._threads: list[Thread] = []

    def init(self) -> None:
        import gpiod
        from gpiod.line import Bias, Direction, Value

        if self._direction == GPIODirection.INPUT:
            settings = gpiod.LineSettings(
                direction=Direction.INPUT,
                bias=Bias.PULL_DOWN,
            )
        else:
            settings = gpiod.LineSettings(
                direction=Direction.OUTPUT,
                output_value=Value.INACTIVE,
            )

        self._request = gpiod.request_lines(
            self._chip,
            consumer="evo-gpio",
            config={self._pin: settings},
        )
        log.info("GPIORpi '%s' initialized on pin %d (%s)", self._name, self._pin, self._direction)

    def close(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=1.0)
        self._threads.clear()
        if self._request is not None:
            self._request.release()
            self._request = None

    def _check_init(self) -> None:
        if self._request is None:
            raise RuntimeError("GPIO not initialized, call init() first")

    def read(self) -> Task[bool]:
        self._check_init()
        if self._direction != GPIODirection.INPUT:
            return ImmediateErrorTask(NotImplementedError("read() requires INPUT direction"))
        from gpiod.line import Value

        return ImmediateResultTask(self._request.get_value(self._pin) == Value.ACTIVE)

    def write(self, state: bool) -> Task[None]:
        self._check_init()
        if self._direction != GPIODirection.OUTPUT:
            return ImmediateErrorTask(NotImplementedError("write() requires OUTPUT direction"))
        from gpiod.line import Value

        self._request.set_value(self._pin, Value.ACTIVE if state else Value.INACTIVE)
        return ImmediateResultTask(None)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        self._check_init()
        if self._direction != GPIODirection.INPUT:
            raise NotImplementedError("interrupt() requires INPUT direction")
        event: Event[bool] = Event()

        def _watch() -> None:
            import gpiod
            from gpiod.line import Bias, Direction, Edge

            edge_map = {
                GPIOEdge.RISING: Edge.RISING,
                GPIOEdge.FALLING: Edge.FALLING,
                GPIOEdge.BOTH: Edge.BOTH,
            }
            # Reconfigure the line to enable kernel-level edge detection
            self._request.reconfigure_lines(
                config={
                    self._pin: gpiod.LineSettings(
                        direction=Direction.INPUT,
                        bias=Bias.PULL_DOWN,
                        edge_detection=edge_map[edge],
                    )
                }
            )

            while not self._stop.is_set():
                # Block until an edge event or timeout (to check _stop)
                if self._request.wait_edge_events(timeout=timedelta(seconds=0.5)):
                    for ev in self._request.read_edge_events():
                        is_rising = ev.event_type == ev.Type.RISING_EDGE
                        event.trigger(is_rising)

        t = Thread(target=_watch, daemon=True)
        t.start()
        self._threads.append(t)
        return event
