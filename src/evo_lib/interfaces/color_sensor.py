"""Abstract interface for RGBC color sensors."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.peripheral import Placable
from evo_lib.types.color import NamedColor

if TYPE_CHECKING:
    from evo_lib.task import Task
    from evo_lib.types.color import ColorRaw


class ColorSensor(Placable):
    """An RGBC color sensor with classification, optional LED illumination and software gamma."""

    commands = DriverCommands()

    @abstractmethod
    @commands.register(
        args=[],
        result=[
            ("r", ArgTypes.U16(help="Red ADC counts")),
            ("g", ArgTypes.U16(help="Green ADC counts")),
            ("b", ArgTypes.U16(help="Blue ADC counts")),
            ("c", ArgTypes.U16(help="Clear ADC counts")),
        ],
    )
    def read_color(self) -> Task[ColorRaw]:
        """Read one raw RGBC sample straight off the sensor."""

    @abstractmethod
    @commands.register(
        args=[],
        result=[("name", ArgTypes.Enum(NamedColor, help="Closest palette entry"))],
    )
    def get_color(self) -> Task[NamedColor]:
        """Classify the current reading against the palette."""

    @abstractmethod
    @commands.register(
        args=[
            ("name", ArgTypes.Enum(NamedColor, help="Palette entry to set")),
            ("r", ArgTypes.U16(help="Red ADC counts")),
            ("g", ArgTypes.U16(help="Green ADC counts")),
            ("b", ArgTypes.U16(help="Blue ADC counts")),
            ("c", ArgTypes.U16(help="Clear ADC counts")),
        ],
        result=[],
    )
    def set_color(self, name: NamedColor, r: int, g: int, b: int, c: int) -> Task[()]:
        """Register a palette reference for ``name`` from known RGBC counts."""

    @abstractmethod
    def calibrate(self, name: NamedColor, samples: int = 10) -> Task[()]:
        """Live-sample ``samples`` times and store the average as the palette ref for ``name``.

        Not exposed as a REPL command on real sensors — calibration requires
        physical presentation of a target and is a commissioning operation,
        not a runtime debug knob. Virtual implementations may expose it.
        """

    @abstractmethod
    @commands.register(
        args=[("intensity", ArgTypes.F32(help="0.0-1.0; 0 if no LED is wired"))],
        result=[],
    )
    def set_light(self, intensity: float) -> Task[()]:
        """Set the on-board LED brightness (no-op if no LED is wired)."""

    @abstractmethod
    @commands.register(
        args=[],
        result=[("intensity", ArgTypes.F32(help="Last commanded intensity (0.0-1.0)"))],
    )
    def get_light(self) -> Task[float]:
        """Return the LED brightness (0.0 if no LED is wired)."""

    @abstractmethod
    @commands.register(
        args=[("gamma", ArgTypes.F32(help="Software gamma (>0); 1.0 = off"))],
        result=[],
    )
    def set_gamma(self, gamma: float) -> Task[()]:
        """Set the software gamma applied before classification."""

    @abstractmethod
    @commands.register(
        args=[],
        result=[("gamma", ArgTypes.F32(help="Current software gamma"))],
    )
    def get_gamma(self) -> Task[float]:
        """Return the current software gamma."""
