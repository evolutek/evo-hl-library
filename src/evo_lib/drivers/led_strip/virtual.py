"""LedStrip drivers: virtual implementations for testing and simulation."""

import logging

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.interfaces.led_strip import LedStrip
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.color import Color


class LedStripVirtual(LedStrip):
    """In-memory LED strip for tests and simulation."""

    def __init__(
        self,
        name: str,
        num_pixels: int,
        brightness: float = 0.5,
        logger: logging.Logger | None = None,
    ):
        super().__init__(name)
        self._num_pixels = num_pixels
        self._brightness = max(0.0, min(1.0, brightness))
        self._log = logger or logging.getLogger(__name__)
        self.pixels: list[Color] = [Color(0.0, 0.0, 0.0) for _ in range(num_pixels)]

    def init(self) -> None:
        self._log.info("LedStripVirtual '%s' initialized: %d pixels", self.name, self._num_pixels)

    def close(self) -> None:
        pass

    def set_pixel(self, index: int, color: Color) -> None:
        self.pixels[index] = color

    def get_pixel(self, index: int) -> Color:
        return self.pixels[index]

    def fill(self, color: Color) -> None:
        self.pixels = [color] * self._num_pixels

    def set_brightness(self, brightness: float) -> None:
        self._brightness = max(0.0, min(1.0, brightness))

    def get_brightness(self) -> float:
        return self._brightness

    def show(self) -> Task[None]:
        return ImmediateResultTask(None)

    def clear(self) -> Task[None]:
        self.fill(Color(0.0, 0.0, 0.0))
        return ImmediateResultTask(None)

    @property
    def num_pixels(self) -> int:
        return self._num_pixels


class LedStripVirtualDefinition(DriverDefinition):
    """Factory for LedStripVirtual from config args."""

    def __init__(self, logger: Logger):
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        defn.add_required("num_pixels", ArgTypes.U16())
        defn.add_optional("brightness", ArgTypes.F32(), 0.5)
        return defn

    def create(self, args: DriverInitArgs) -> LedStripVirtual:
        name = args.get("name")
        return LedStripVirtual(
            name=name,
            num_pixels=args.get("num_pixels"),
            brightness=args.get("brightness"),
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
