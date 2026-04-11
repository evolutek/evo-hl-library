"""Tirette driver: real (GPIO-based) and virtual implementations."""

from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIODirection, GPIOEdge
from evo_lib.logger import Logger
from evo_lib.peripheral import Placable
from evo_lib.task import ImmediateResultTask, Task

if TYPE_CHECKING:
    from evo_lib.drivers.gpio.rpi import RpiGPIOVirtual


class Tirette(Placable):
    """Real tirette: listens to a GPIO interrupt to detect pull/put."""

    commands = DriverCommands()

    def __init__(self, name: str, logger: Logger, gpio: GPIO, active_state: bool):
        super().__init__(name)
        self._logger = logger
        self._gpio = gpio
        self._active_state = active_state

    def init(self) -> Task[()]:
        self._gpio.init()
        return ImmediateResultTask()

    def close(self) -> None:
        self._gpio.close()

    def get_trigger_event(self) -> Event[bool]:
        """Return an event with an argument at True if the tirette is pulled."""
        return self._gpio.interrupt(GPIOEdge.BOTH).transform(lambda x: (x != self._active_state,))

    @commands.register(
        args=[],
        result=[("active_state", ArgTypes.Bool(help="True if the tirette is in place (GPIO at active state)"))],
    )
    def get_state(self) -> Task[bool]:
        """Return True if the tirette is in its active state (in place)."""
        gpio_state = self._gpio.read().wait()[0]
        return ImmediateResultTask(gpio_state == self._active_state)


class TiretteDefinition(DriverDefinition):
    """Factory for real Tirette. Creates an RpiGPIO internally from the pin number."""

    def __init__(self, logger: Logger):
        super().__init__(Tirette.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("pin", ArgTypes.U8())
        defn.add_required(
            "active_state", ArgTypes.Bool(help="True means the tirette is in place when GPIO is high")
        )
        return defn

    def create(self, args: DriverInitArgs) -> Tirette:
        from evo_lib.drivers.gpio.rpi import RpiGPIO

        gpio = RpiGPIO(
            name=f"{args.get_name()}_gpio",
            logger=self._logger,
            pin=args.get("pin"),
            direction=GPIODirection.INPUT,
        )
        return Tirette(args.get_name(), self._logger, gpio, args.get("active_state"))


class TiretteVirtual(Tirette):
    """Virtual tirette for simulation. Adds pull/put commands to inject GPIO state."""

    commands = DriverCommands(parents=[Tirette.commands])

    def __init__(self, name: str, logger: Logger, gpio: "RpiGPIOVirtual", active_state: bool):
        super().__init__(name, logger, gpio, active_state)
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
    """Factory for TiretteVirtual. Creates an RpiGPIOVirtual internally."""

    def __init__(self, logger: Logger):
        super().__init__(TiretteVirtual.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("pin", ArgTypes.U8())
        defn.add_required(
            "active_state", ArgTypes.Bool(help="True means the tirette is in place when GPIO is high")
        )
        return defn

    def create(self, args: DriverInitArgs) -> TiretteVirtual:
        from evo_lib.drivers.gpio.rpi import RpiGPIOVirtual

        gpio = RpiGPIOVirtual(
            name=f"{args.get_name()}_gpio",
            logger=self._logger,
            pin=args.get("pin"),
            direction=GPIODirection.INPUT,
        )
        return TiretteVirtual(args.get_name(), self._logger, gpio, args.get("active_state"))
