"""GPIO drivers: virtual implementations for testing and simulation."""

import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition, DriverCommands
from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIODirection, GPIOEdge
from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.task import ImmediateErrorTask, ImmediateResultTask, Task

NUM_MCP23017_PINS = 16


class GPIOPinVirtual(GPIO):
    """In-memory GPIO for tests and simulation, one pin per instance."""

    commands = DriverCommands([GPIO.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        direction: GPIODirection,
        pull_up: bool = False,
        pin: int = 0,
    ):
        super().__init__(name)
        self._pin = pin
        self._direction = direction
        self._pull_up = pull_up
        self._log = logger
        self._lock = threading.Lock()
        self._initialized = False
        self._state: bool = False
        self._events: dict[GPIOEdge, Event[bool]] = {
            GPIOEdge.RISING: Event(),
            GPIOEdge.FALLING: Event(),
            GPIOEdge.BOTH: Event(),
        }

    def _check_ready(self) -> None:
        if not self._initialized:
            raise RuntimeError("GPIO not initialized, call init() first")

    def init(self) -> Task[()]:
        self._initialized = True
        self._state = False
        self._event = None
        self._log.info(f"GPIOPinVirtual '{self.name}' initialized (pin {self._pin}, {self._direction})",)
        return ImmediateResultTask()

    def close(self) -> None:
        self._initialized = False
        self._state = False
        self._event = None

    def read(self) -> Task[bool]:
        # Works on both INPUT and OUTPUT pins. On OUTPUT, returns the last
        # value written — matches RPi.GPIO behavior and lets tests assert
        # on what a driver has written to a virtual output pin.
        self._check_ready()
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
        return self._events[edge]

    @commands.register(args = [
        ("state", ArgTypes.Bool())
    ])
    def inject_input(self, state: bool) -> None:
        """Inject a value for testing. Triggers the interrupt event if active."""
        with self._lock:
            if state == self._state:
                return
            self._state = state
        if state:
            self._events[GPIOEdge.RISING].trigger(state)
            self._events[GPIOEdge.BOTH].trigger(state)
        else:
            self._events[GPIOEdge.FALLING].trigger(state)
            self._events[GPIOEdge.BOTH].trigger(state)


class GPIOPinVirtualDefinition(DriverDefinition):
    def __init__(self, logger: Logger):
        super().__init__(GPIOPinVirtual.commands)
        self._logger = logger

    def create(self, args: DriverInitArgs) -> Peripheral:
        return  GPIOPinVirtual(
            args.get_name(),
            self._logger,
            args.get("direction"),
            args.get("pull_up")
        )

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        args = DriverInitArgsDefinition()
        args.add_required("direction", ArgTypes.Enum(GPIODirection))
        args.add_optional("pull_up", ArgTypes.Bool(), False)
        return args


class GPIOChipVirtual(InterfaceHolder):
    """In-memory virtual for the MCP23017 chip, for tests and simulation.

    Creates GPIOPinVirtual instances for each pin, sharing the same GPIO interface.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        address: int = 0x20,
    ):
        super().__init__(name)
        self._log = logger
        self._address = address
        self._pins: dict[int, GPIOPinVirtual] = {}

    def init(self) -> Task[()]:
        self._log.info(f"MCP23017 virtual '{self.name}' initialized at 0x{self._address:02x}")
        return ImmediateResultTask()

    def close(self) -> None:
        self._pins.clear()
        self._log.info(f"MCP23017 virtual '{self.name}' closed")

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
        virtual_pin = GPIOPinVirtual(name, self._log, direction, pull_up, pin)
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
