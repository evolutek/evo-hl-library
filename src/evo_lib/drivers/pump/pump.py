from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral, Placable
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task


class Pump(Placable):
    """Listens to a GPIO interrupt to detect pull/put events.

    The GPIO is injected and managed externally (by the PeripheralsManager).
    ``debounce_s`` filters mechanical bouncing on insertion/removal: only
    a state stable for ``debounce_s`` is propagated to listeners.
    """

    commands = DriverCommands()

    def __init__(self, name: str, logger: Logger, pump_gpio: GPIO, ev_gpio: GPIO | None):
        super().__init__(name)
        self._logger = logger
        self._pump_gpio = pump_gpio
        self._ev_gpio = ev_gpio

    def init(self) -> Task[()]:
        # TODO: Check if GPIO are in output direction
        return ImmediateResultTask()

    def close(self) -> None:
        pass

    @commands.register(args=[], result=[])
    def grab(self) -> Task[()]:
        self._pump_gpio.write(True)
        if self._ev_gpio is not None:
            self._ev_gpio.write(True)
        return ImmediateResultTask()

    @commands.register(args=[], result=[])
    def drop(self) -> Task[()]:
        self._pump_gpio.write(False)
        if self._ev_gpio is not None:
            self._ev_gpio.write(False)
        return ImmediateResultTask()


class PumpDefinition(DriverDefinition):
    """Factory for Pump. Takes a GPIO peripheral by reference."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(Pump.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("pump_gpio", ArgTypes.Component(GPIO, self._peripherals))
        defn.add_optional("ev_gpio", ArgTypes.Component(GPIO, self._peripherals), None)
        return defn

    def create(self, args: DriverInitArgs) -> Pump:
        return Pump(
            args.get_name(),
            self._logger,
            args.get("pump_gpio"),
            args.get("ev_gpio"),
        )
