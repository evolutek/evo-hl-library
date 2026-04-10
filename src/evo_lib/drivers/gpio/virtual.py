"""GPIO drivers: virtual implementations for testing and simulation."""

import logging
import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIODirection, GPIOEdge
from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.task import ImmediateErrorTask, ImmediateResultTask, Task

NUM_MCP23017_PINS = 16


class GPIOPinVirtual(GPIO):
    """In-memory GPIO for tests and simulation, one pin per instance."""

    def __init__(
        self,
        name: str,
        pin: int,
        direction: GPIODirection = GPIODirection.INPUT,
        pull_up: bool = False,
        logger: logging.Logger | None = None,
    ):
        super().__init__(name)
        self._pin = pin
        self._direction = direction
        self._pull_up = pull_up
        self._log = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._initialized = False
        self._state: bool = False
        self._event: Event[bool] | None = None
        self._edge: GPIOEdge = GPIOEdge.BOTH

    def _check_ready(self) -> None:
        if not self._initialized:
            raise RuntimeError("GPIO not initialized, call init() first")

    def init(self) -> None:
        self._initialized = True
        self._state = False
        self._event = None
        self._log.info(
            "GPIOPinVirtual '%s' initialized (pin %d, %s)",
            self.name,
            self._pin,
            self._direction,
        )

    def close(self) -> None:
        self._initialized = False
        self._state = False
        self._event = None

    def read(self) -> Task[bool]:
        self._check_ready()
        if self._direction != GPIODirection.INPUT:
            return ImmediateErrorTask(NotImplementedError("read() requires INPUT direction"))
        return ImmediateResultTask(self._state)

    def write(self, state: bool) -> Task[None]:
        self._check_ready()
        if self._direction != GPIODirection.OUTPUT:
            return ImmediateErrorTask(NotImplementedError("write() requires OUTPUT direction"))
        self._state = state
        return ImmediateResultTask(None)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        self._check_ready()
        if self._direction != GPIODirection.INPUT:
            raise NotImplementedError("interrupt() requires INPUT direction")
        self._edge = edge
        self._event = Event()
        return self._event

    def inject_input(self, value: bool) -> None:
        """Inject a value for testing. Triggers the interrupt event if active."""
        with self._lock:
            old = self._state
            self._state = value
            event = self._event
            edge = self._edge
        if event is not None and value != old:
            fire = (
                edge == GPIOEdge.BOTH
                or (edge == GPIOEdge.RISING and value)
                or (edge == GPIOEdge.FALLING and not value)
            )
            if fire:
                event.trigger(value)


class GPIOChipVirtual(InterfaceHolder):
    """In-memory virtual for the MCP23017 chip, for tests and simulation.

    Creates GPIOPinVirtual instances for each pin, sharing the same GPIO interface.
    """

    def __init__(
        self,
        name: str,
        address: int = 0x20,
        logger: logging.Logger | None = None,
    ):
        super().__init__(name)
        self._address = address
        self._log = logger or logging.getLogger(__name__)
        self._pins: dict[int, GPIOPinVirtual] = {}

    def init(self) -> None:
        self._log.info("MCP23017 virtual '%s' initialized at 0x%02x", self.name, self._address)

    def close(self) -> None:
        self._pins.clear()
        self._log.info("MCP23017 virtual '%s' closed", self.name)

    def get_subcomponents(self) -> list[Peripheral]:
        """Return all pins that have been created via get_pin."""
        return list(self._pins.values())

    def get_pin(
        self,
        pin: int,
        name: str,
        direction: GPIODirection = GPIODirection.INPUT,
        pull_up: bool = False,
    ) -> GPIOPinVirtual:
        """Create or retrieve a GPIOPinVirtual for the given pin number."""
        if not 0 <= pin < NUM_MCP23017_PINS:
            raise ValueError(f"Pin {pin} out of range (0-{NUM_MCP23017_PINS - 1})")
        if pin in self._pins:
            return self._pins[pin]
        virtual_pin = GPIOPinVirtual(name, pin, direction, pull_up, logger=self._log)
        self._pins[pin] = virtual_pin
        return virtual_pin


class GPIOChipVirtualDefinition(DriverDefinition):
    """Factory for GPIOChipVirtual from config args."""

    def __init__(self, logger: Logger):
        super().__init__()
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        defn.add_optional("address", ArgTypes.U8(), 0x20)
        return defn

    def create(self, args: DriverInitArgs) -> GPIOChipVirtual:
        name = args.get("name")
        return GPIOChipVirtual(
            name=name,
            address=args.get("address"),
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
