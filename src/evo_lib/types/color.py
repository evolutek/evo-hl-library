"""Color types and a small named palette for RGBC sensor classification.

Three distinct types live here, each with a single purpose:

- ``ColorRaw``   — raw RGBC ADC counts straight from a sensor (ints 0-65535)
- ``Color``      — continuous RGBC value, normalized floats 0.0-1.0 (LED pixels,
                   rendering, anything that needs a value rather than a label)
- ``NamedColor`` — enum of palette names (Red, Green, ...) used by sensor
                   classification. Default reference RGBC values are NOT
                   provided here — they are chip-specific and live in the
                   relevant driver (e.g. ``tcs34725.py``).
"""

from enum import IntEnum


class ColorRaw:
    """Raw RGBC ADC counts straight from a color sensor.

    Values are unsigned integers whose range depends on the sensor
    configuration (typical full-scale: 0 to 65535 for TCS34725-family
    chips, but actually capped by ATIME to ``(256 - ATIME) * 1024``).
    """

    __slots__ = ("r", "g", "b", "c")

    def __init__(self, r: int, g: int, b: int, c: int) -> None:
        self.r = r
        self.g = g
        self.b = b
        self.c = c


class Color:
    """RGBC color: red, green, blue + clear (unfiltered / brightness) channel.

    The fourth channel ``c`` is the "Clear" channel as defined by TCS34725-style
    RGBC sensors — an unfiltered photodiode that captures overall luminous
    intensity. It is NOT an alpha transparency. For contexts where only RGB
    matters (e.g. LED strips), ``c`` can safely be left at its default of 1.0.
    """

    __slots__ = ("r", "g", "b", "c")

    def __init__(self, r: float, g: float, b: float, c: float = 1.0) -> None:
        self.r = r
        self.g = g
        self.b = b
        self.c = c

    @staticmethod
    def from_rgb_int(val: int) -> "Color":
        r = (val >> 16) & 0xFF
        g = (val >>  8) & 0xFF
        b = (val      ) & 0xFF
        return Color(r / 255.0, g / 255.0, b / 255.0)

    @staticmethod
    def from_rgbc_int(val: int) -> "Color":
        """Parse a packed 0xRRGGBBCC integer into a Color."""
        r = (val >> 24) & 0xFF
        g = (val >> 16) & 0xFF
        b = (val >>  8) & 0xFF
        c = (val      ) & 0xFF
        return Color(r / 255.0, g / 255.0, b / 255.0, c / 255.0)

    @staticmethod
    def from_raw(raw: ColorRaw, full_scale: int = 65535) -> "Color":
        """Normalize raw ADC counts to a Color with each channel in 0.0-1.0.

        ``full_scale`` is the sensor's current max count. For TCS34725-style
        chips this depends on ATIME — pass ``sensor.get_full_scale()`` rather
        than relying on the 65535 default when accuracy matters.
        """
        fs = float(full_scale) if full_scale > 0 else 1.0
        return Color(
            min(1.0, raw.r / fs),
            min(1.0, raw.g / fs),
            min(1.0, raw.b / fs),
            min(1.0, raw.c / fs),
        )


class NamedColor(IntEnum):
    """Hardcoded palette of names used by color-sensor classification.

    Reference RGBC counts for each name are supplied by the chip driver
    (different chip families have wildly different responsivity and
    full-scale, so a one-size palette would be meaningless).
    """

    Unknown = 0
    Black = 1
    White = 2
    Red = 3
    Green = 4
    Blue = 5
    Yellow = 6


class Palette:
    """Mutable mapping ``NamedColor`` → reference ``ColorRaw``.

    ``classify`` picks the entry with the smallest squared euclidean
    distance to the measured raw value (sqrt skipped — monotone, so the
    ranking is identical and cheaper to compute).

    Optional gamma correction: when ``gamma != 1.0`` each channel is
    transformed by ``v ** (1/gamma)`` before comparison. The gamma-corrected
    references are cached, so the runtime cost stays at 4 ``pow`` calls
    per classify (only on the live measurement).
    """

    def __init__(
        self,
        refs: dict[NamedColor, ColorRaw] | None = None,
        gamma: float = 1.0,
    ) -> None:
        self._refs: dict[NamedColor, ColorRaw] = dict(refs) if refs else {}
        self._gamma: float = gamma
        self._refs_gamma: dict[NamedColor, tuple[float, float, float, float]] | None = None
        self._refresh_gamma_cache()

    def set(self, name: NamedColor, raw: ColorRaw) -> None:
        self._refs[name] = raw
        self._refresh_gamma_cache()

    def get(self, name: NamedColor) -> ColorRaw | None:
        return self._refs.get(name)

    def get_gamma(self) -> float:
        return self._gamma

    def set_gamma(self, gamma: float) -> None:
        if gamma <= 0:
            raise ValueError(f"gamma must be > 0, got {gamma}")
        self._gamma = gamma
        self._refresh_gamma_cache()

    def classify(
        self,
        raw: ColorRaw,
        max_distance_squared: float | None = None,
    ) -> NamedColor:
        """Return the closest ``NamedColor`` (by squared euclidean distance).

        Empty palette or all entries beyond ``max_distance_squared`` returns
        ``NamedColor.Unknown``.
        """
        if not self._refs:
            return NamedColor.Unknown

        best_name = NamedColor.Unknown
        best_dist: float = float("inf")

        if self._refs_gamma is None:
            # Fast path: integer arithmetic, no pow calls.
            for name, ref in self._refs.items():
                if name is NamedColor.Unknown:
                    continue
                dr = raw.r - ref.r
                dg = raw.g - ref.g
                db = raw.b - ref.b
                dc = raw.c - ref.c
                dist = dr * dr + dg * dg + db * db + dc * dc
                if dist < best_dist:
                    best_dist = dist
                    best_name = name
        else:
            inv_g = 1.0 / self._gamma
            lr, lg, lb, lc = (raw.r ** inv_g, raw.g ** inv_g,
                              raw.b ** inv_g, raw.c ** inv_g)
            for name, (rr, gg, bb, cc) in self._refs_gamma.items():
                if name is NamedColor.Unknown:
                    continue
                dr = lr - rr
                dg = lg - gg
                db = lb - bb
                dc = lc - cc
                dist = dr * dr + dg * dg + db * db + dc * dc
                if dist < best_dist:
                    best_dist = dist
                    best_name = name

        if max_distance_squared is not None and best_dist > max_distance_squared:
            return NamedColor.Unknown
        return best_name

    def _refresh_gamma_cache(self) -> None:
        if self._gamma == 1.0:
            self._refs_gamma = None
            return
        inv_g = 1.0 / self._gamma
        self._refs_gamma = {
            name: (ref.r ** inv_g, ref.g ** inv_g, ref.b ** inv_g, ref.c ** inv_g)
            for name, ref in self._refs.items()
        }
