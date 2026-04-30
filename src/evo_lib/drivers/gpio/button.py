"""Button driver: wraps a GPIO INPUT to detect press/release transitions.

Both Button and ButtonVirtual take a GPIO peripheral by reference;
they do not instantiate their own GPIO. This lets a button sit on any
GPIO source (RPi, MCP23017, virtual, ...) chosen in config.

For the soft-power case (single physical button driving both a shutdown
signal and a power-latch output), use ``power_button.py`` instead.
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


class Button(Placable):
    """Listens to a GPIO interrupt to detect press/release events.

    The GPIO is injected and managed externally (by the PeripheralsManager).
    ``debounce_s`` filters mechanical bouncing on press/release: only a
    state stable for ``debounce_s`` is propagated to listeners.
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
        """Return an event with an argument at True when the button is pressed."""
        event = self._gpio.interrupt(GPIOEdge.BOTH).transform(
            lambda x: (x == self._active_state,)
        )
        if self._debounce_s > 0:
            event = event.debounce(self._debounce_s)
        return event

    @commands.register(
        args=[],
        result=[("pressed", ArgTypes.Bool(help="True if the button is currently pressed"))],
    )
    def is_pressed(self) -> Task[bool]:
        """Return True if the button is currently in its active state."""
        gpio_state = self._gpio.read().wait()[0]
        return ImmediateResultTask(gpio_state == self._active_state)


class ButtonDefinition(DriverDefinition):
    """Factory for Button. Takes a GPIO peripheral by reference."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(Button.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("gpio", ArgTypes.Component(GPIO, self._peripherals))
        defn.add_required(
            "active_state",
            ArgTypes.Bool(help="True means the button reads HIGH when pressed (active-high)"),
        )
        defn.add_optional(
            "debounce_s",
            ArgTypes.F32(help="Stability window (s) for mechanical bouncing"),
            0.0,
        )
        return defn

    def create(self, args: DriverInitArgs) -> Button:
        return Button(
            args.get_name(),
            self._logger,
            args.get("gpio"),
            args.get("active_state"),
            args.get("debounce_s"),
        )


class ButtonVirtual(Button):
    """Virtual button: same as Button but adds press/release simulation commands.

    Requires a GPIOPinVirtual (which exposes inject_input) rather than any
    GPIO interface.
    """

    commands = DriverCommands(parents=[Button.commands])

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
    def press(self) -> Task[()]:
        """Simulate pressing the button."""
        self._virtual_gpio.inject_input(self._active_state)
        self._logger.info(f"Button '{self.name}' pressed (simulated)")
        return ImmediateResultTask()

    @commands.register(args=[], result=[])
    def release(self) -> Task[()]:
        """Simulate releasing the button."""
        self._virtual_gpio.inject_input(not self._active_state)
        self._logger.info(f"Button '{self.name}' released (simulated)")
        return ImmediateResultTask()


class ButtonVirtualDefinition(DriverDefinition):
    """Factory for ButtonVirtual. Takes a GPIOPinVirtual peripheral by reference."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(ButtonVirtual.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("gpio", ArgTypes.Component(GPIOPinVirtual, self._peripherals))
        defn.add_required(
            "active_state",
            ArgTypes.Bool(help="True means the button reads HIGH when pressed (active-high)"),
        )
        defn.add_optional(
            "debounce_s",
            ArgTypes.F32(help="Stability window (s) for mechanical bouncing"),
            0.0,
        )
        return defn

    def create(self, args: DriverInitArgs) -> ButtonVirtual:
        return ButtonVirtual(
            args.get_name(),
            self._logger,
            args.get("gpio"),
            args.get("active_state"),
            args.get("debounce_s"),
        )
