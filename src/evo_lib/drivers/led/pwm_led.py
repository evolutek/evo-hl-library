"""LED driver: wraps a PWM channel into an intensity-controlled LED.

The same single-file layout as ``tirette.py`` / ``tcs34725.py``: real driver,
its config-driven Definition, the virtual twin, and its Definition all live
together because there is only one concrete implementation strategy.
"""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.led import LED
from evo_lib.interfaces.pwm import PWM
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task


class PWMLed(LED):
    """A LED driven by a PWM channel.

    ``intensity`` is mapped 1:1 onto the underlying PWM's duty cycle, so any
    PWM implementation (PCA9685, RPi GPIO, virtual) works.
    """

    commands = DriverCommands(parents=[LED.commands])

    def __init__(self, name: str, logger: Logger, pwm: PWM):
        super().__init__(name)
        self._log = logger
        self._pwm = pwm
        self._last_intensity: float = 0.0

    def init(self) -> Task[()]:
        # PWM dependency lifecycle is handled by the PeripheralsManager.
        return ImmediateResultTask()

    def close(self) -> None:
        pass

    def set_intensity(self, intensity: float) -> Task[()]:
        intensity = max(0.0, min(1.0, intensity))
        self._last_intensity = intensity
        return self._pwm.set_duty_cycle(intensity)

    def get_intensity(self) -> Task[float]:
        return ImmediateResultTask(self._last_intensity)


class PWMLedDefinition(DriverDefinition):
    """Factory for PWMLed. Resolves the PWM channel by name from the registry."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(PWMLed.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("pwm", ArgTypes.Component(PWM, self._peripherals))
        return defn

    def create(self, args: DriverInitArgs) -> PWMLed:
        name = args.get_name()
        return PWMLed(
            name=name,
            logger=self._logger.get_sublogger(name),
            pwm=args.get("pwm"),
        )


class PWMLedVirtual(PWMLed):
    """Drop-in twin of PWMLed: virtual-ness comes from the injected PWM
    being a PWMVirtual. Kept as a distinct class so future debug / sim
    hooks (fault injection, snapshots) have a place to live without
    touching the real driver — same convention as PWMServoVirtual."""

    commands = DriverCommands(parents=[PWMLed.commands])


class PWMLedVirtualDefinition(DriverDefinition):
    """Factory for PWMLedVirtual."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(PWMLedVirtual.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("pwm", ArgTypes.Component(PWM, self._peripherals))
        return defn

    def create(self, args: DriverInitArgs) -> PWMLedVirtual:
        name = args.get_name()
        return PWMLedVirtual(
            name=name,
            logger=self._logger.get_sublogger(name),
            pwm=args.get("pwm"),
        )
