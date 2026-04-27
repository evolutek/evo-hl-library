"""Abstract interface for addressable LED strips."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.peripheral import Placable

if TYPE_CHECKING:
    from evo_lib.task import Task


class LedStrip(Placable):
    """An addressable RGB LED strip (e.g. WS2812B / NeoPixel).

    Pixel writes (``set_pixel``, ``fill``) are buffered: they only mutate an
    in-memory framebuffer. Call ``show`` to push the buffer to the hardware in
    a single shot — this avoids visible tearing during multi-pixel updates.

    Color values are floats in [0.0, 1.0] (clamped). The Clear / alpha channel
    of the ``Color`` type is ignored here: LED hardware only consumes RGB.
    """

    commands = DriverCommands()

    @abstractmethod
    @commands.register(
        args=[
            ("index", ArgTypes.U16(help="0-based pixel index (< num_pixels)")),
            ("r", ArgTypes.F32(help="Red 0.0-1.0")),
            ("g", ArgTypes.F32(help="Green 0.0-1.0")),
            ("b", ArgTypes.F32(help="Blue 0.0-1.0")),
        ],
        result=[],
    )
    def set_pixel(self, index: int, r: float, g: float, b: float) -> Task[()]:
        """Buffer one pixel; call ``show`` to apply."""

    @abstractmethod
    @commands.register(
        args=[("index", ArgTypes.U16(help="0-based pixel index"))],
        result=[
            ("r", ArgTypes.F32(help="Red 0.0-1.0")),
            ("g", ArgTypes.F32(help="Green 0.0-1.0")),
            ("b", ArgTypes.F32(help="Blue 0.0-1.0")),
        ],
    )
    def get_pixel(self, index: int) -> Task[float, float, float]:
        """Read back the buffered RGB triplet at ``index``."""

    @abstractmethod
    @commands.register(
        args=[
            ("r", ArgTypes.F32(help="Red 0.0-1.0")),
            ("g", ArgTypes.F32(help="Green 0.0-1.0")),
            ("b", ArgTypes.F32(help="Blue 0.0-1.0")),
        ],
        result=[],
    )
    def fill(self, r: float, g: float, b: float) -> Task[()]:
        """Buffer the same color into every pixel; call ``show`` to apply."""

    @abstractmethod
    @commands.register(
        args=[("brightness", ArgTypes.F32(help="Global brightness 0.0-1.0"))],
        result=[],
    )
    def set_brightness(self, brightness: float) -> Task[()]:
        """Set global brightness multiplier (clamped to 0.0-1.0)."""

    @abstractmethod
    @commands.register(
        args=[],
        result=[("brightness", ArgTypes.F32(help="Current brightness 0.0-1.0"))],
    )
    def get_brightness(self) -> Task[float]:
        """Return the current global brightness multiplier."""

    @abstractmethod
    @commands.register(args=[], result=[])
    def show(self) -> Task[()]:
        """Push the pixel buffer to the hardware in one shot."""

    @abstractmethod
    @commands.register(args=[], result=[])
    def clear(self) -> Task[()]:
        """Buffer black on every pixel and ``show`` immediately."""

    @property
    @abstractmethod
    def num_pixels(self) -> int:
        """Number of pixels in the strip."""
