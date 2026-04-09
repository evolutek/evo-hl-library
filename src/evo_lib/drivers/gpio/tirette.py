"""Tirette driver: Take a GPIO instance as initialisation argument."""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIOEdge
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task


class Tirette(GPIO):
    def __init__(
        self,
        name: str,
        logger: Logger,
        gpio: GPIO,
        active_state: bool
    ):
        super().__init__(name)
        self._logger = logger
        self._gpio = gpio
        self._active_state = active_state

    def init(self) -> Task[None]:
        # TODO: Check GPIO direction
        return ImmediateResultTask() # Nothing to do

    def close(self) -> None:
        pass # Nothing to do

    def get_trigger_event(self) -> Event[bool]:
        """Return an event with an argument at True if the tirette is pulled"""
        if self._active_state:
            return self._gpio.interrupt(GPIOEdge.FALLING)
        else:
            return self._gpio.interrupt(GPIOEdge.RISING)


class TiretteDefinition(DriverDefinition):
    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("gpio", ArgTypes.Component(GPIO, self._peripherals))
        defn.add_required("active_state", ArgTypes.Bool(help = "True mean that the tirette is on when GPIO is high"))
        return defn

    def create(self, args: DriverInitArgs) -> Tirette:
        return Tirette(
            args.get_name(),
            self._logger,
            args.get("gpio"),
            args.get("active_state")
        )
