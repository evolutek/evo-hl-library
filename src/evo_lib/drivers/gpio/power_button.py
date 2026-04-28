"""PowerButton driver: soft-power button with shutdown signal + power latch.

A typical Pi/embedded "soft-power" circuit has a single physical button
wired to two GPIO pins:

- ``gpio_int`` (INPUT): asserted when the user presses the button to ask
  the robot to shut down. The driver exposes the press as a debounced Event.
- ``gpio_hold`` (OUTPUT): held HIGH at ``init()`` to keep the robot powered
  on (latch). The driver exposes ``release_power()`` which sets it LOW;
  that physically cuts the robot's power.

The driver intentionally does NOT release power on ``close()``: closing the
peripheral (e.g. lib reload during dev) must not power off the robot. Power
is cut only via the explicit ``release_power()`` command.
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


class PowerButton(Placable):
    """Soft-power button: shutdown event on input, power latch on output.

    The GPIO peripherals are injected and managed externally (by the
    PeripheralsManager). ``active_state`` is the level that ``gpio_int``
    reads when the button is pressed.
    """

    commands = DriverCommands()

    def __init__(
        self,
        name: str,
        logger: Logger,
        gpio_int: GPIO,
        gpio_hold: GPIO,
        active_state: bool,
        debounce_s: float = 0.0,
    ):
        super().__init__(name)
        self._logger = logger
        self._gpio_int = gpio_int
        self._gpio_hold = gpio_hold
        self._active_state = active_state
        self._debounce_s = debounce_s

    def init(self) -> Task[()]:
        # Latch power immediately. The PeripheralsManager initializes both
        # GPIO peripherals before us, so writing here is safe.
        return self._gpio_hold.write(True)

    def close(self) -> None:
        # Intentional: do NOT touch gpio_hold here. close() runs during lib
        # teardown; setting it LOW would power-off the robot on every dev
        # reload. Power is only released via release_power().
        pass

    def get_trigger_event(self) -> Event[()]:
        """Return an event that fires (debounced) on every button press."""
        # Filter to the active edge HW-side: a release is meaningless on a
        # soft-power button (no metric/strategy reacts to it), so we don't
        # waste wakeups on it.
        edge = GPIOEdge.RISING if self._active_state else GPIOEdge.FALLING
        event = self._gpio_int.interrupt(edge).transform(lambda _: ())
        if self._debounce_s > 0:
            event = event.debounce(self._debounce_s)
        return event

    @commands.register(
        args=[],
        result=[("pressed", ArgTypes.Bool(help="True if the button is currently pressed"))],
    )
    def is_pressed(self) -> Task[bool]:
        """Return True if the button is currently in its active state."""
        gpio_state = self._gpio_int.read().wait()[0]
        return ImmediateResultTask(gpio_state == self._active_state)

    @commands.register(args=[], result=[])
    def release_power(self) -> Task[None]:
        """Release the power latch — the robot will physically power off."""
        self._logger.warning(
            f"PowerButton '{self.name}': releasing power latch — robot is shutting down"
        )
        return self._gpio_hold.write(False)


class PowerButtonDefinition(DriverDefinition):
    """Factory for PowerButton. Takes two GPIO peripherals by reference."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(PowerButton.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("gpio_int", ArgTypes.Component(GPIO, self._peripherals))
        defn.add_required("gpio_hold", ArgTypes.Component(GPIO, self._peripherals))
        defn.add_required(
            "active_state",
            ArgTypes.Bool(help="True means gpio_int reads HIGH on press (active-high)"),
        )
        defn.add_optional(
            "debounce_s",
            ArgTypes.F32(help="Stability window (s) for mechanical bouncing"),
            0.0,
        )
        return defn

    def create(self, args: DriverInitArgs) -> PowerButton:
        return PowerButton(
            args.get_name(),
            self._logger,
            args.get("gpio_int"),
            args.get("gpio_hold"),
            args.get("active_state"),
            args.get("debounce_s"),
        )


class PowerButtonVirtual(PowerButton):
    """Virtual PowerButton: adds press/release simulation on the int line.

    Requires GPIOPinVirtual peripherals for both ``gpio_int`` and ``gpio_hold``
    — the hold pin is kept in the signature for parity with the real driver
    even though the simulated press/release commands only stimulate the int
    line. Tests that want to assert on the latch state read ``gpio_hold``
    directly.
    """

    commands = DriverCommands(parents=[PowerButton.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        gpio_int: GPIOPinVirtual,
        gpio_hold: GPIOPinVirtual,
        active_state: bool,
        debounce_s: float = 0.0,
    ):
        super().__init__(name, logger, gpio_int, gpio_hold, active_state, debounce_s)
        self._virtual_int = gpio_int

    @commands.register(args=[], result=[])
    def press(self) -> Task[()]:
        """Simulate pressing the power button."""
        self._virtual_int.inject_input(self._active_state)
        self._logger.info(f"PowerButton '{self.name}' pressed (simulated)")
        return ImmediateResultTask()

    @commands.register(args=[], result=[])
    def release(self) -> Task[()]:
        """Simulate releasing the power button."""
        self._virtual_int.inject_input(not self._active_state)
        self._logger.info(f"PowerButton '{self.name}' released (simulated)")
        return ImmediateResultTask()


class PowerButtonVirtualDefinition(DriverDefinition):
    """Factory for PowerButtonVirtual."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(PowerButtonVirtual.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("gpio_int", ArgTypes.Component(GPIOPinVirtual, self._peripherals))
        defn.add_required("gpio_hold", ArgTypes.Component(GPIOPinVirtual, self._peripherals))
        defn.add_required(
            "active_state",
            ArgTypes.Bool(help="True means gpio_int reads HIGH on press (active-high)"),
        )
        defn.add_optional(
            "debounce_s",
            ArgTypes.F32(help="Stability window (s) for mechanical bouncing"),
            0.0,
        )
        return defn

    def create(self, args: DriverInitArgs) -> PowerButtonVirtual:
        return PowerButtonVirtual(
            args.get_name(),
            self._logger,
            args.get("gpio_int"),
            args.get("gpio_hold"),
            args.get("active_state"),
            args.get("debounce_s"),
        )
