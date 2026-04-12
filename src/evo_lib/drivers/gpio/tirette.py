"""Tirette driver: wraps a GPIO interface to detect pull/put transitions.

Both Tirette and TiretteVirtual take a GPIO peripheral by reference;
they do not instantiate their own GPIO. This lets a tirette sit on any
GPIO source (RPi, MCP23017, virtual, ...) chosen in config.
"""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.drivers.gpio.virtual import GPIOPinVirtual
from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIOEdge
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral, Placable
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task


class Tirette(Placable):
    """Listens to a GPIO interrupt to detect pull/put events.

    The GPIO is injected and managed externally (by the PeripheralsManager).
    ``debounce_s`` filters mechanical bouncing on insertion/removal: only
    a state stable for ``debounce_s`` is propagated to listeners.
    """

    commands = DriverCommands()

    def __init__(
        self,
        name: str,
        logger: Logger,
        gpio: GPIO,
        active_state: bool,
        debounce_s: float = 0.0,
    ):
        super().__init__(name)
        self._logger = logger
        self._gpio = gpio
        self._active_state = active_state
        self._debounce_s = debounce_s

    def init(self) -> Task[()]:
        # GPIO dependency is initialized by the PeripheralsManager.
        return ImmediateResultTask()

    def close(self) -> None:
        # GPIO dependency is closed by the PeripheralsManager.
        pass

    def get_trigger_event(self) -> Event[bool]:
        """Return an event with an argument at True if the tirette is pulled."""
        event = self._gpio.interrupt(GPIOEdge.BOTH).transform(
            lambda x: (x != self._active_state,)
        )
        if self._debounce_s > 0:
            event = event.debounce(self._debounce_s)
        return event

    @commands.register(
        args=[],
        result=[("active_state", ArgTypes.Bool(help="True if the tirette is in place (GPIO at active state)"))],
    )
    def get_state(self) -> Task[bool]:
        """Return True if the tirette is in its active state (in place)."""
        gpio_state = self._gpio.read().wait()[0]
        return ImmediateResultTask(gpio_state == self._active_state)


class TiretteDefinition(DriverDefinition):
    """Factory for Tirette. Takes a GPIO peripheral by reference."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(Tirette.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("gpio", ArgTypes.Component(GPIO, self._peripherals))
        defn.add_required(
            "active_state", ArgTypes.Bool(help="True means the tirette is in place when GPIO is high")
        )
        defn.add_optional(
            "debounce_s", ArgTypes.F32(help="Stability window (s) for mechanical bouncing"), 0.0
        )
        return defn

    def create(self, args: DriverInitArgs) -> Tirette:
        return Tirette(
            args.get_name(),
            self._logger,
            args.get("gpio"),
            args.get("active_state"),
            args.get("debounce_s"),
        )


class TiretteVirtual(Tirette):
    """Virtual tirette: same as Tirette but adds pull/put simulation commands.

    Requires a GPIOPinVirtual (which exposes inject_input) rather than any
    GPIO interface.
    """

    commands = DriverCommands(parents=[Tirette.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        gpio: GPIOPinVirtual,
        active_state: bool,
        debounce_s: float = 0.0,
    ):
        super().__init__(name, logger, gpio, active_state, debounce_s)
        self._virtual_gpio = gpio

    @commands.register(args=[], result=[])
    def pull(self) -> Task[()]:
        """Simulate pulling the tirette out."""
        self._virtual_gpio.inject_input(not self._active_state)
        self._logger.info(f"Tirette '{self.name}' pulled (simulated)")
        return ImmediateResultTask()

    @commands.register(args=[], result=[])
    def put(self) -> Task[()]:
        """Simulate putting the tirette back in."""
        self._virtual_gpio.inject_input(self._active_state)
        self._logger.info(f"Tirette '{self.name}' put back (simulated)")
        return ImmediateResultTask()


class TiretteVirtualDefinition(DriverDefinition):
    """Factory for TiretteVirtual. Takes a GPIOPinVirtual peripheral by reference."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(TiretteVirtual.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("gpio", ArgTypes.Component(GPIOPinVirtual, self._peripherals))
        defn.add_required(
            "active_state", ArgTypes.Bool(help="True means the tirette is in place when GPIO is high")
        )
        defn.add_optional(
            "debounce_s", ArgTypes.F32(help="Stability window (s) for mechanical bouncing"), 0.0
        )
        return defn

    def create(self, args: DriverInitArgs) -> TiretteVirtual:
        return TiretteVirtual(
            args.get_name(),
            self._logger,
            args.get("gpio"),
            args.get("active_state"),
            args.get("debounce_s"),
        )
