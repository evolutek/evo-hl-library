"""WS2812B (NeoPixel) addressable LED strip via rpi_ws281x.

The WS2812B uses a single-wire 800 kHz protocol with strict timing that the
Pi cannot bit-bang reliably from user space. The ``rpi_ws281x`` C library
handles it via PWM/PCM/SPI DMA depending on the GPIO pin chosen:

- GPIO 12, 18 → PWM channel 0 (default)
- GPIO 13, 19 → PWM channel 1
- GPIO 21     → PCM
- GPIO 10     → SPI MOSI (no root required, but SPI must be enabled)

Same single-file layout as ``tcs34725.py`` / ``pwm_led.py``: real driver,
its config-driven Definition, the virtual twin, and its Definition all live
together.

The hardware-touching code is funneled through ``_hw_*`` hook methods so
subclasses (``WS2812BVirtual``, ``MdbLed`` -> ``MdbLedVirtual``) can swap
the rpi_ws281x backend out for an in-memory buffer without re-implementing
the public ``LedStrip`` API on top.
"""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.led_strip import LedStrip
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task

# Lazy-loaded inside _hw_init_strip() so this module imports on dev machines
# without rpi_ws281x installed (it's an optional rpi extra).
_ws = None

_DEFAULT_FREQUENCY_HZ = 800_000
_DEFAULT_DMA_CHANNEL = 10
_DEFAULT_PIN = 12  # PWM0; matches legacy WS2812BLedStrip(42, board.D12, 36, 1.0)


def _clamp_unit(v: float) -> float:
    return 0.0 if v < 0.0 else 1.0 if v > 1.0 else v


def _pack_rgb(r: float, g: float, b: float) -> int:
    """Pack three normalized [0,1] floats into a 0xRRGGBB 24-bit int."""
    rb = round(_clamp_unit(r) * 255)
    gb = round(_clamp_unit(g) * 255)
    bb = round(_clamp_unit(b) * 255)
    return (rb << 16) | (gb << 8) | bb


def _unpack_rgb(packed: int) -> tuple[float, float, float]:
    return (
        ((packed >> 16) & 0xFF) / 255.0,
        ((packed >>  8) & 0xFF) / 255.0,
        ((packed      ) & 0xFF) / 255.0,
    )


class WS2812B(LedStrip):
    """WS2812B / NeoPixel strip driven by rpi_ws281x DMA."""

    commands = DriverCommands(parents=[LedStrip.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        num_pixels: int,
        pin: int = _DEFAULT_PIN,
        brightness: float = 1.0,
        frequency_hz: int = _DEFAULT_FREQUENCY_HZ,
        dma_channel: int = _DEFAULT_DMA_CHANNEL,
    ):
        super().__init__(name)
        if num_pixels <= 0:
            raise ValueError(f"num_pixels must be > 0, got {num_pixels}")
        self._log = logger
        self._num_pixels = num_pixels
        self._pin = pin
        self._brightness = _clamp_unit(brightness)
        self._frequency_hz = frequency_hz
        self._dma_channel = dma_channel
        self._strip = None  # set by _hw_init_strip on real hardware

    def init(self) -> Task[()]:
        self._hw_init_strip()
        self._log.info(
            f"{type(self).__name__} '{self.name}' initialized: "
            f"{self._num_pixels} px on GPIO {self._pin} "
            f"(freq={self._frequency_hz} Hz, dma={self._dma_channel}, "
            f"brightness={self._brightness:.2f})"
        )
        return ImmediateResultTask()

    def close(self) -> None:
        self._hw_close_strip()
        self._log.info(f"{type(self).__name__} '{self.name}' closed")

    def set_pixel(self, index: int, r: float, g: float, b: float) -> Task[()]:
        if not 0 <= index < self._num_pixels:
            raise IndexError(
                f"pixel index {index} out of range [0, {self._num_pixels})"
            )
        self._hw_set_pixel(index, _pack_rgb(r, g, b))
        return ImmediateResultTask()

    def get_pixel(self, index: int) -> Task[float, float, float]:
        if not 0 <= index < self._num_pixels:
            raise IndexError(
                f"pixel index {index} out of range [0, {self._num_pixels})"
            )
        r, g, b = _unpack_rgb(self._hw_get_pixel(index))
        return ImmediateResultTask(r, g, b)

    def fill(self, r: float, g: float, b: float) -> Task[()]:
        packed = _pack_rgb(r, g, b)
        for i in range(self._num_pixels):
            self._hw_set_pixel(i, packed)
        return ImmediateResultTask()

    def set_brightness(self, brightness: float) -> Task[()]:
        self._brightness = _clamp_unit(brightness)
        self._hw_set_brightness(round(self._brightness * 255))
        return ImmediateResultTask()

    def get_brightness(self) -> Task[float]:
        return ImmediateResultTask(self._brightness)

    def show(self) -> Task[()]:
        self._hw_show()
        return ImmediateResultTask()

    def clear(self) -> Task[()]:
        self.fill(0.0, 0.0, 0.0).wait()
        return self.show()

    @property
    def num_pixels(self) -> int:
        return self._num_pixels

    # --- Hardware boundary -------------------------------------------------
    # Virtual subclasses override these to swap rpi_ws281x out for an
    # in-memory buffer. The public API above is purely arithmetic + dispatch.

    def _hw_init_strip(self) -> None:
        global _ws
        if _ws is None:
            import rpi_ws281x  # lazy: only required on the actual robot

            _ws = rpi_ws281x

        self._strip = _ws.PixelStrip(
            num=self._num_pixels,
            pin=self._pin,
            freq_hz=self._frequency_hz,
            dma=self._dma_channel,
            invert=False,
            brightness=round(self._brightness * 255),
            channel=0,
            strip_type=_ws.WS2811_STRIP_GRB,
        )
        self._strip.begin()

    def _hw_close_strip(self) -> None:
        if self._strip is None:
            return
        # Best-effort blackout so a crash doesn't leave the robot lit.
        for i in range(self._num_pixels):
            self._strip.setPixelColor(i, 0)
        self._strip.show()

    def _hw_set_pixel(self, index: int, packed: int) -> None:
        self._strip.setPixelColor(index, packed)

    def _hw_get_pixel(self, index: int) -> int:
        return self._strip.getPixelColor(index)

    def _hw_show(self) -> None:
        self._strip.show()

    def _hw_set_brightness(self, byte_value: int) -> None:
        self._strip.setBrightness(byte_value)


class WS2812BDefinition(DriverDefinition):
    """Factory for ``WS2812B`` from JSON5 config."""

    def __init__(self, logger: Logger):
        super().__init__(WS2812B.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("num_pixels", ArgTypes.U16(help="Number of LEDs in the strip"))
        defn.add_optional("pin", ArgTypes.U8(help="GPIO pin (BCM)"), _DEFAULT_PIN)
        defn.add_optional("brightness", ArgTypes.F32(help="Initial brightness 0.0-1.0"), 1.0)
        defn.add_optional(
            "frequency_hz",
            ArgTypes.U32(help="Bit clock; 800 kHz for WS2812B"),
            _DEFAULT_FREQUENCY_HZ,
        )
        defn.add_optional(
            "dma_channel",
            ArgTypes.U8(help="DMA channel (avoid 0 — kernel uses it for SD)"),
            _DEFAULT_DMA_CHANNEL,
        )
        return defn

    def create(self, args: DriverInitArgs) -> WS2812B:
        name = args.get_name()
        return WS2812B(
            name=name,
            logger=self._logger.get_sublogger(name),
            num_pixels=args.get("num_pixels"),
            pin=args.get("pin"),
            brightness=args.get("brightness"),
            frequency_hz=args.get("frequency_hz"),
            dma_channel=args.get("dma_channel"),
        )


class WS2812BVirtual(WS2812B):
    """In-memory WS2812B twin: same constructor surface as the real driver,
    so swapping real↔virtual in config is a one-line change.

    The DMA-related arguments (``pin``, ``frequency_hz``, ``dma_channel``)
    are kept for **signature parity** with ``WS2812B`` and intentionally
    ignored — orthogonal to simulation. Do not "simplify" them away.

    The wire format (packed 0xRRGGBB ints) matches the real driver, so
    tests can compare bit-exact.
    """

    commands = DriverCommands(parents=[WS2812B.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        num_pixels: int,
        pin: int = _DEFAULT_PIN,
        brightness: float = 1.0,
        frequency_hz: int = _DEFAULT_FREQUENCY_HZ,
        dma_channel: int = _DEFAULT_DMA_CHANNEL,
    ):
        super().__init__(name, logger, num_pixels, pin, brightness, frequency_hz, dma_channel)
        # Buffer (set by set_pixel/fill) and shown frame (set by show), as
        # packed 0xRRGGBB ints.
        self._buffer: list[int] = [0] * num_pixels
        self._shown: list[int] = [0] * num_pixels
        # Brightness as a 0-255 byte, mirroring rpi_ws281x's internal storage.
        self._brightness_byte: int = round(self._brightness * 255)

    def _hw_init_strip(self) -> None:
        # No hardware to acquire.
        pass

    def _hw_close_strip(self) -> None:
        pass

    def _hw_set_pixel(self, index: int, packed: int) -> None:
        self._buffer[index] = packed

    def _hw_get_pixel(self, index: int) -> int:
        return self._buffer[index]

    def _hw_show(self) -> None:
        self._shown = list(self._buffer)

    def _hw_set_brightness(self, byte_value: int) -> None:
        self._brightness_byte = byte_value

    # --- Test helpers, virtual-only ------------------------------------

    def get_shown_frame(self) -> list[tuple[float, float, float]]:
        """Return the last frame pushed via ``show`` as RGB triplets.

        Lets tests assert the user actually called ``show`` after buffering
        — buffer-only writes won't show up here.
        """
        return [_unpack_rgb(p) for p in self._shown]


class WS2812BVirtualDefinition(DriverDefinition):
    """Factory for ``WS2812BVirtual``. Mirrors ``WS2812BDefinition`` so the
    config can swap real↔virtual by changing only the driver name."""

    def __init__(self, logger: Logger):
        super().__init__(WS2812BVirtual.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("num_pixels", ArgTypes.U16(help="Number of LEDs in the strip"))
        defn.add_optional("pin", ArgTypes.U8(help="GPIO pin (BCM, ignored)"), _DEFAULT_PIN)
        defn.add_optional("brightness", ArgTypes.F32(help="Initial brightness 0.0-1.0"), 1.0)
        defn.add_optional(
            "frequency_hz",
            ArgTypes.U32(help="Bit clock (ignored)"),
            _DEFAULT_FREQUENCY_HZ,
        )
        defn.add_optional(
            "dma_channel",
            ArgTypes.U8(help="DMA channel (ignored)"),
            _DEFAULT_DMA_CHANNEL,
        )
        return defn

    def create(self, args: DriverInitArgs) -> WS2812BVirtual:
        name = args.get_name()
        return WS2812BVirtual(
            name=name,
            logger=self._logger.get_sublogger(name),
            num_pixels=args.get("num_pixels"),
            pin=args.get("pin"),
            brightness=args.get("brightness"),
            frequency_hz=args.get("frequency_hz"),
            dma_channel=args.get("dma_channel"),
        )
