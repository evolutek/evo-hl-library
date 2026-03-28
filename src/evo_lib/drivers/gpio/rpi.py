"""GPIO driver: real Raspberry Pi implementation via gpiod (libgpiod v2)."""

import threading
from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING

from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIODirection, GPIOEdge
from evo_lib.logger import Logger
from evo_lib.task import ImmediateErrorTask, ImmediateResultTask, Task

# gpiod import is delayed until init() is called
gpiod = None

if TYPE_CHECKING:
    import gpiod as gpiod_type
    gpiod = gpiod_type


# Default chip path (gpiochip0 on Pi 3/4, gpiochip4 on Pi 5)
DEFAULT_GPIOD_CHIP = "/dev/gpiochip0"


class RPiGPIODefinition(DriverDefinition):
    def __init__(self, logger: Logger):
        super().__init__()
        self._logger = logger

    def create(self, args: DriverInitArgs) -> RPiGPIO:
        return RPiGPIO(
            args.get("name"),
            self._logger.get_sublogger("rpi_gpio"),
            args.get("pin"),
            args.get("direction", GPIODirection.INPUT),
            args.get("chip", DEFAULT_GPIOD_CHIP),
        )


class RPiGPIOMode(Enum):
    INPUT = "input"
    INPUT_PULLUP = "input_pulldown"
    INPUT_PULLDOWN = "input_pullup"
    OUTPUT = "output"


class RPiGPIO(GPIO):
    """Native BCM GPIO on Raspberry Pi via gpiod, one pin per instance."""

    def __init__(
        self,
        name: str,
        logger: Logger,
        pin: int,
        mode: RPiGPIOMode = RPiGPIOMode.INPUT,
        chip: str = DEFAULT_GPIOD_CHIP
    ):
        super().__init__(name)
        self._logger = logger
        self._pin = pin
        self._mode = mode
        self._settings: gpiod_type.LineSettings | None = None
        self._chip: gpiod_type.Chip = chip
        self._request: gpiod_type.LineRequest = None
        self._stop = threading.Event()
        self._watch_thread: threading.Thread | None = None
        self._events: dict[GPIOEdge, Event[bool]] = {
            GPIOEdge.RISING: Event(),
            GPIOEdge.FALLING: Event(),
            GPIOEdge.BOTH: Event(),
        }

    def init(self) -> Task[None]:
        global gpiod
        if gpiod is None:
            import gpiod as gpiod_module
            gpiod = gpiod_module

        if self._mode == RPiGPIOMode.OUTPUT:
            self._settings = gpiod.LineSettings(
                direction=gpiod.line.Direction.OUTPUT,
                output_value=gpiod.line.Value.INACTIVE,
            )

        else:
            bias = gpiod.line.Bias.DISABLED
            if self._mode == RPiGPIOMode.INPUT_PULLUP:
                bias = gpiod.line.Bias.PULL_UP
            elif self._mode == RPiGPIOMode.INPUT_PULLDOWN:
                bias = gpiod.line.Bias.PULL_DOWN

            self._settings = gpiod.LineSettings(
                direction=gpiod.line.Direction.INPUT,
                bias=bias,
            )

        self._request = gpiod.request_lines(
            self._chip,
            consumer="evo-gpio",
            config={self._pin: self._settings},
        )

        # self._logger.info(f"'{self._name}' initialized on pin {self._pin} ({self._mode})")

        return ImmediateResultTask()

    def close(self) -> None:
        self._stop.set()
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=1.0)
        if self._watch_thread.is_alive():
            raise RuntimeError("Timeout when trying to join ")
        else:
            self._watch_thread = None

        if self._request is not None:
            self._request.release()
            self._request = None

    def _check_init(self) -> None:
        if self._request is None:
            raise RuntimeError("GPIO not initialized, call init() first")

    def read(self) -> Task[bool]:
        self._check_init()
        if self._mode == RPiGPIOMode.OUTPUT:
            return ImmediateErrorTask(NotImplementedError("read() requires INPUT direction"))
        return ImmediateResultTask(self._request.get_value(self._pin) == gpiod.line.Value.ACTIVE)

    def write(self, state: bool) -> Task[None]:
        self._check_init()
        if self._mode != RPiGPIOMode.OUTPUT:
            return ImmediateErrorTask(NotImplementedError("write() requires OUTPUT direction"))
        self._request.set_value(self._pin, gpiod.line.Value.ACTIVE if state else gpiod.line.Value.INACTIVE)
        return ImmediateResultTask(None)

    def _watch(self) -> None:
        # Reconfigure the line to enable kernel-level edge detection
        self._settings.edge_detection = gpiod.line.Edge.BOTH
        self._request.reconfigure_lines(
            config = {self._pin: self._settings}
        )

        while not self._stop.is_set():
            # Block until an edge event or timeout (to check _stop)
            if self._request.wait_edge_events(timeout=timedelta(seconds=0.2)):
                for ev in self._request.read_edge_events():
                    is_rising = ev.event_type == ev.Type.RISING_EDGE
                    if is_rising:
                        self._events[GPIOEdge.RISING].trigger(is_rising)
                    else:
                        self._events[GPIOEdge.FALLING].trigger(is_rising)
                    self._events[GPIOEdge.BOTH].trigger(is_rising)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        self._check_init()
        if self._mode == RPiGPIOMode.OUTPUT:
            raise NotImplementedError("interrupt() requires INPUT direction")

        if self._watch_thread is None:
            self._watch_thread = threading.Thread(target=self._watch)
            self._watch_thread.start()

        return self._events[edge]
