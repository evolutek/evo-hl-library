"""GPIO driver: real Raspberry Pi implementation via gpiod (libgpiod v2)."""

import os
import selectors
import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIODirection, GPIOEdge
from evo_lib.logger import Logger
from evo_lib.task import ImmediateErrorTask, ImmediateResultTask, Task

# Lazy-loaded in init() so this module can be imported without gpiod installed
_gpiod = None

# Default chip path (gpiochip0 on Pi 3/4, gpiochip4 on Pi 5)
DEFAULT_CHIP = "/dev/gpiochip0"


class RpiGPIO(GPIO):
    """Native BCM GPIO on Raspberry Pi via gpiod, one pin per instance."""

    def __init__(
        self,
        name: str,
        logger: Logger,
        pin: int,
        direction: GPIODirection = GPIODirection.INPUT,
        chip: str = DEFAULT_CHIP,
    ):
        super().__init__(name)
        self._pin = pin
        self._direction = direction
        self._chip_path = chip
        self._log = logger
        self._request = None
        self._stop_r, self._stop_w = os.pipe()
        self._watch_thread: threading.Thread | None = None
        self._events: dict[GPIOEdge, Event[bool]] = {}

    def init(self) -> None:
        global _gpiod
        if _gpiod is None:
            import gpiod
            _gpiod = gpiod

        if self._direction == GPIODirection.INPUT:
            settings = _gpiod.LineSettings(
                direction=_gpiod.line.Direction.INPUT,
                bias=_gpiod.line.Bias.DISABLED,
            )
        else:
            settings = _gpiod.LineSettings(
                direction=_gpiod.line.Direction.OUTPUT,
                output_value=_gpiod.line.Value.INACTIVE,
            )

        self._request = _gpiod.request_lines(
            self._chip_path,
            consumer="evo-gpio",
            config={self._pin: settings},
        )
        self._log.info(f"RpiGPIO '{self.name}' initialized on pin {self._pin} ({self._direction})")

    def close(self) -> None:
        if self._stop_w < 0:
            return
        # Signal the watch thread to stop by writing to the pipe
        os.write(self._stop_w, b"\x00")
        if self._watch_thread is not None:
            self._watch_thread.join(timeout=2.0)
            if self._watch_thread.is_alive():
                self._log.warning(f"GPIO watch thread for pin {self._pin} did not stop in time")
            self._watch_thread = None
        if self._request is not None:
            self._request.release()
            self._request = None
        os.close(self._stop_r)
        os.close(self._stop_w)
        self._stop_r, self._stop_w = -1, -1

    def _check_ready(self) -> None:
        if self._request is None:
            raise RuntimeError("GPIO not initialized, call init() first")

    def read(self) -> Task[bool]:
        self._check_ready()
        if self._direction != GPIODirection.INPUT:
            return ImmediateErrorTask(NotImplementedError("read() requires INPUT direction"))
        return ImmediateResultTask(self._request.get_value(self._pin) == _gpiod.line.Value.ACTIVE)

    def write(self, state: bool) -> Task[None]:
        self._check_ready()
        if self._direction != GPIODirection.OUTPUT:
            return ImmediateErrorTask(NotImplementedError("write() requires OUTPUT direction"))
        value = _gpiod.line.Value.ACTIVE if state else _gpiod.line.Value.INACTIVE
        self._request.set_value(self._pin, value)
        return ImmediateResultTask(None)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        self._check_ready()
        if self._direction != GPIODirection.INPUT:
            raise NotImplementedError("interrupt() requires INPUT direction")

        if edge not in self._events:
            self._events[edge] = Event()

        # Start the watch thread on first interrupt() call
        if self._watch_thread is None:
            self._request.reconfigure_lines(
                config={
                    self._pin: _gpiod.LineSettings(
                        direction=_gpiod.line.Direction.INPUT,
                        edge_detection=_gpiod.line.Edge.BOTH,
                    )
                }
            )
            self._watch_thread = threading.Thread(
                target=self._watch, daemon=True, name=f"gpio-watch-{self._pin}"
            )
            self._watch_thread.start()

        return self._events[edge]

    def _watch(self) -> None:
        """Wait for edge events using selectors (no timeout polling)."""
        sel = selectors.DefaultSelector()
        sel.register(self._request.fd, selectors.EVENT_READ, "gpio")
        sel.register(self._stop_r, selectors.EVENT_READ, "stop")
        try:
            while True:
                for key, _ in sel.select():
                    if key.data == "stop":
                        return
                    for ev in self._request.read_edge_events():
                        is_rising = ev.event_type == ev.Type.RISING_EDGE
                        if is_rising and GPIOEdge.RISING in self._events:
                            self._events[GPIOEdge.RISING].trigger(True)
                        elif not is_rising and GPIOEdge.FALLING in self._events:
                            self._events[GPIOEdge.FALLING].trigger(False)
                        if GPIOEdge.BOTH in self._events:
                            self._events[GPIOEdge.BOTH].trigger(is_rising)
        finally:
            sel.close()


class RpiGPIODefinition(DriverDefinition):
    """Factory for RpiGPIO from config args."""

    def __init__(self, logger: Logger):
        super().__init__()
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("pin", ArgTypes.U8())
        defn.add_optional("direction", ArgTypes.Enum(GPIODirection), GPIODirection.INPUT)
        defn.add_optional("chip", ArgTypes.String(), DEFAULT_CHIP)
        return defn

    def create(self, args: DriverInitArgs) -> RpiGPIO:
        return RpiGPIO(
            name=args.get_name(),
            logger=self._logger,
            pin=args.get("pin"),
            direction=args.get("direction"),
            chip=args.get("chip"),
        )
