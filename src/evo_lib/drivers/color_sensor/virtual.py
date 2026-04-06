"""ColorSensor drivers: virtual implementations for testing and simulation."""

import logging

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.interfaces.color_sensor import ColorSensor
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.color import Color


class ColorSensorVirtual(ColorSensor):
    """In-memory color sensor for tests and simulation."""

    def __init__(self, name: str, logger: logging.Logger | None = None):
        super().__init__(name)
        self._log = logger or logging.getLogger(__name__)
        self._color = Color(0.0, 0.0, 0.0)
        self._power_color: float = 1.0
        self._min_color: float = 0.0
        self._max_color: float = 1.0

    def init(self) -> None:
        self._log.info("ColorSensorVirtual '%s' initialized", self.name)

    def close(self) -> None:
        pass

    def read_color(self) -> Task[Color]:
        return ImmediateResultTask(self._color)

    def calibrate(self, power_color: float, min_color: float, max_color: float) -> None:
        self._power_color = power_color
        self._min_color = min_color
        self._max_color = max_color

    def inject_color(self, color: Color) -> None:
        """Set the color value returned by read_color (for testing)."""
        self._color = color


class ColorSensorVirtualDefinition(DriverDefinition):
    """Factory for ColorSensorVirtual from config args."""

    def __init__(self, logger: Logger):
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        return defn

    def create(self, args: DriverInitArgs) -> ColorSensorVirtual:
        name = args.get("name")
        return ColorSensorVirtual(
            name=name,
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
