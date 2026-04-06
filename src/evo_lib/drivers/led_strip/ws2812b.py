"""WS2812B driver: addressable LED strip via rpi_ws281x (DMA-based).

The WS2812B (NeoPixel) uses a single-wire protocol with strict timing.
The rpi_ws281x library handles this via DMA on the Raspberry Pi.
"""

import logging

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.interfaces.led_strip import LedStrip
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.color import Color

# Lazy-loaded in init() so this module can be imported without rpi_ws281x installed
_ws = None


class WS2812B(LedStrip):
    """Addressable LED strip via rpi_ws281x."""

    def __init__(
        self,
        name: str,
        pin: int,
        num_pixels: int,
        brightness: float = 0.5,
        logger: logging.Logger | None = None,
    ):
        super().__init__(name)
        self._pin = pin
        self._num_pixels = num_pixels
        self._brightness = max(0.0, min(1.0, brightness))
        self._log = logger or logging.getLogger(__name__)
        self._strip = None

    def init(self) -> None:
        global _ws
        if _ws is None:
            import rpi_ws281x

            _ws = rpi_ws281x

        self._strip = _ws.PixelStrip(
            self._num_pixels,
            self._pin,
            brightness=round(self._brightness * 255),
        )
        self._strip.begin()
        self._log.info(
            "WS2812B '%s' initialized: %d pixels on GPIO %d",
            self.name,
            self._num_pixels,
            self._pin,
        )

    def close(self) -> None:
        if self._strip is not None:
            for i in range(self._num_pixels):
                self._strip.setPixelColor(i, 0)
            self._strip.show()
            self._log.info("WS2812B '%s' closed", self.name)

    def set_pixel(self, index: int, color: Color) -> None:
        r, g, b = round(color.r * 255), round(color.g * 255), round(color.b * 255)
        self._strip.setPixelColor(index, (r << 16) | (g << 8) | b)

    def get_pixel(self, index: int) -> Color:
        val = self._strip.getPixelColor(index)
        return Color.from_rgb_int(val)

    def fill(self, color: Color) -> None:
        for i in range(self._num_pixels):
            self.set_pixel(i, color)

    def set_brightness(self, brightness: float) -> None:
        self._brightness = max(0.0, min(1.0, brightness))
        self._strip.setBrightness(round(self._brightness * 255))

    def get_brightness(self) -> float:
        return self._brightness

    def show(self) -> Task[None]:
        self._strip.show()
        return ImmediateResultTask(None)

    def clear(self) -> Task[None]:
        self.fill(Color(0.0, 0.0, 0.0))
        return self.show()

    @property
    def num_pixels(self) -> int:
        return self._num_pixels


class WS2812BDefinition(DriverDefinition):
    """Factory for WS2812B from config args."""

    def __init__(self, logger: Logger):
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        defn.add_required("pin", ArgTypes.U8())
        defn.add_required("num_pixels", ArgTypes.U16())
        defn.add_optional("brightness", ArgTypes.F32(), 0.5)
        return defn

    def create(self, args: DriverInitArgs) -> WS2812B:
        name = args.get("name")
        return WS2812B(
            name=name,
            pin=args.get("pin"),
            num_pixels=args.get("num_pixels"),
            brightness=args.get("brightness"),
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
