"""Color representation types and the ``Color`` composite.

Five representation classes cover the useful encodings of a single color:

- ``ColorRGBC(r, g, b, c, full_scale)`` — raw ADC counts from RGBC sensors (ints)
- ``ColorRGB(r, g, b)``                 — normalized RGB in 0.0-1.0 (LED pixels, rendering)
- ``ColorHSV(h, s, v)``                 — Hue ∈ [0,360), S/V ∈ [0,1] (classification, UI)
- ``ColorChroma(rc, gc, bc)``           — r/c, g/c, b/c ratios (≈ intensity-invariant)
- ``ColorHex(value)``                   — 0xRRGGBB packed int (logs, config, humans)

``Color`` is a composite: it stores one "source" representation (the one passed to
its factory) and derives the others lazily on first property access. Cache is
per-instance, so repeated reads are O(1).

⚠ Not all conversions are bijective. In particular:

- ``Chroma → RGB`` loses the absolute intensity (V). The derivation assumes the
  maximum channel is 1.0 — this is a convention, not a measurement.
- ``HSV → RGBC`` needs a ``full_scale`` to map V into integer ADC counts. The
  default 255 is a display-space choice, not a sensor-space one.

For classification, always work in the native space of the source (Hue for
illuminant robustness, Chroma for intensity-invariance). Only use the derived
reprs for display/logging or when the conversion is known to be lossless.
"""

from __future__ import annotations

from enum import IntEnum
from math import isclose


# ── Representation classes ───────────────────────────────────────────────

class ColorRGBC:
    """Raw RGBC ADC counts straight off an RGBC sensor (TCS34725 family, etc.).

    ``full_scale`` is the chip's current max possible count, which depends on
    integration time: for TCS34725 it caps at ``(256 - ATIME) * 1024`` (max
    65535). Carrying it on the instance lets downstream conversions normalize
    correctly regardless of the sensor's current exposure.
    """

    __slots__ = ("r", "g", "b", "c", "full_scale")

    def __init__(self, r: int, g: int, b: int, c: int, full_scale: int = 65535) -> None:
        self.r = r
        self.g = g
        self.b = b
        self.c = c
        self.full_scale = full_scale

    def __repr__(self) -> str:
        return (
            f"ColorRGBC(r={self.r}, g={self.g}, b={self.b}, c={self.c},"
            f" full_scale={self.full_scale})"
        )

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ColorRGBC)
            and self.r == other.r
            and self.g == other.g
            and self.b == other.b
            and self.c == other.c
        )

    def to_rgb(self) -> "ColorRGB":
        fs = float(self.full_scale) if self.full_scale > 0 else 1.0
        return ColorRGB(
            min(1.0, self.r / fs),
            min(1.0, self.g / fs),
            min(1.0, self.b / fs),
        )

    def to_hsv(self) -> "ColorHSV":
        # Hue and saturation are ratio-based: independent of full_scale.
        # V is the max channel normalized by full_scale (the Clear channel
        # carries total luminous energy separately — not used here).
        r, g, b = self.r, self.g, self.b
        cmax = max(r, g, b)
        cmin = min(r, g, b)
        delta = cmax - cmin
        if delta == 0:
            h = 0.0
        elif cmax == r:
            h = (60.0 * ((g - b) / delta)) % 360
        elif cmax == g:
            h = 60.0 * ((b - r) / delta) + 120
        else:
            h = 60.0 * ((r - g) / delta) + 240
        s = 0.0 if cmax == 0 else delta / cmax
        v = cmax / float(self.full_scale) if self.full_scale > 0 else 0.0
        return ColorHSV(h, s, min(1.0, v))

    def to_chroma(self) -> "ColorChroma":
        """Divide each channel by Clear. Near-black (c ≈ 0) returns (0, 0, 0).

        Chroma is largely invariant to ambient *intensity* (doubling the light
        doubles r, g, b AND c → ratios unchanged) but remains sensitive to
        spectral shifts (tungsten vs daylight reshapes r/c and b/c unequally).
        """
        if self.c <= 0:
            return ColorChroma(0.0, 0.0, 0.0)
        inv = 1.0 / self.c
        return ColorChroma(self.r * inv, self.g * inv, self.b * inv)

    def to_hex(self) -> "ColorHex":
        return self.to_rgb().to_hex()


class ColorRGB:
    """Normalized RGB with each channel in 0.0-1.0.

    The canonical "display" representation: LED pixels, rendering, mixing.
    No Clear channel — intensity lives in the magnitude of the triplet itself.
    """

    __slots__ = ("r", "g", "b")

    def __init__(self, r: float, g: float, b: float) -> None:
        self.r = r
        self.g = g
        self.b = b

    def __repr__(self) -> str:
        return f"ColorRGB(r={self.r:.3f}, g={self.g:.3f}, b={self.b:.3f})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ColorRGB)
            and isclose(self.r, other.r, abs_tol=1e-6)
            and isclose(self.g, other.g, abs_tol=1e-6)
            and isclose(self.b, other.b, abs_tol=1e-6)
        )

    def to_hsv(self) -> "ColorHSV":
        r, g, b = self.r, self.g, self.b
        cmax = max(r, g, b)
        cmin = min(r, g, b)
        delta = cmax - cmin
        if delta == 0:
            h = 0.0
        elif cmax == r:
            h = (60.0 * ((g - b) / delta)) % 360
        elif cmax == g:
            h = 60.0 * ((b - r) / delta) + 120
        else:
            h = 60.0 * ((r - g) / delta) + 240
        s = 0.0 if cmax == 0 else delta / cmax
        v = cmax
        return ColorHSV(h, s, v)

    def to_rgbc(self, full_scale: int = 255) -> ColorRGBC:
        """Quantize to integer ADC counts. Clear derived as ``max(r,g,b)*full_scale`` — approximation."""
        r_i = max(0, min(full_scale, round(self.r * full_scale)))
        g_i = max(0, min(full_scale, round(self.g * full_scale)))
        b_i = max(0, min(full_scale, round(self.b * full_scale)))
        c_i = max(0, min(full_scale, round(max(self.r, self.g, self.b) * full_scale)))
        return ColorRGBC(r_i, g_i, b_i, c_i, full_scale=full_scale)

    def to_hex(self) -> "ColorHex":
        r = max(0, min(255, round(self.r * 255)))
        g = max(0, min(255, round(self.g * 255)))
        b = max(0, min(255, round(self.b * 255)))
        return ColorHex((r << 16) | (g << 8) | b)

    def to_chroma(self, clear: float | None = None) -> "ColorChroma":
        """Chroma from normalized RGB. If ``clear`` is None, uses ``max(r,g,b)`` as a proxy for C."""
        c = clear if clear is not None else max(self.r, self.g, self.b)
        if c <= 0:
            return ColorChroma(0.0, 0.0, 0.0)
        inv = 1.0 / c
        return ColorChroma(self.r * inv, self.g * inv, self.b * inv)


class ColorHSV:
    """Hue in [0, 360), saturation and value in [0, 1]."""

    __slots__ = ("h", "s", "v")

    def __init__(self, h: float, s: float, v: float) -> None:
        # Normalize h once on construction so downstream comparisons don't drift.
        self.h = h % 360.0
        self.s = s
        self.v = v

    def __repr__(self) -> str:
        return f"ColorHSV(h={self.h:.1f}°, s={self.s:.3f}, v={self.v:.3f})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ColorHSV)
            and isclose(self.h, other.h, abs_tol=1e-3)
            and isclose(self.s, other.s, abs_tol=1e-6)
            and isclose(self.v, other.v, abs_tol=1e-6)
        )

    def to_rgb(self) -> ColorRGB:
        """Standard HSV → RGB (h in degrees)."""
        h, s, v = self.h, self.s, self.v
        if s == 0:
            return ColorRGB(v, v, v)
        c = v * s
        hh = (h / 60.0) % 6.0
        x = c * (1 - abs(hh % 2 - 1))
        if hh < 1:
            r, g, b = c, x, 0.0
        elif hh < 2:
            r, g, b = x, c, 0.0
        elif hh < 3:
            r, g, b = 0.0, c, x
        elif hh < 4:
            r, g, b = 0.0, x, c
        elif hh < 5:
            r, g, b = x, 0.0, c
        else:
            r, g, b = c, 0.0, x
        m = v - c
        return ColorRGB(r + m, g + m, b + m)

    def to_hex(self) -> "ColorHex":
        return self.to_rgb().to_hex()


class ColorChroma:
    """Channel-wise ratios r/c, g/c, b/c from an RGBC reading.

    Dividing each color channel by Clear removes the common intensity factor:
    a 2× brighter light doubles r, g, b AND c → ratios unchanged. This is
    the cheapest way to make classification insensitive to how bright the
    illuminant is. It does NOT remove spectral shifts (a warm tungsten vs a
    cool daylight projector still reshape r/c vs b/c differently) — pair
    with a flash-differential measurement at the sensor to cover that.
    """

    __slots__ = ("rc", "gc", "bc")

    def __init__(self, rc: float, gc: float, bc: float) -> None:
        self.rc = rc
        self.gc = gc
        self.bc = bc

    def __repr__(self) -> str:
        return f"ColorChroma(rc={self.rc:.3f}, gc={self.gc:.3f}, bc={self.bc:.3f})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, ColorChroma)
            and isclose(self.rc, other.rc, abs_tol=1e-6)
            and isclose(self.gc, other.gc, abs_tol=1e-6)
            and isclose(self.bc, other.bc, abs_tol=1e-6)
        )

    def to_rgb(self, v: float = 1.0) -> ColorRGB:
        """Reconstruct RGB, scaling by ``v``. The absolute intensity is lost in chroma; caller supplies it."""
        m = max(self.rc, self.gc, self.bc, 1e-9)
        scale = v / m
        return ColorRGB(
            min(1.0, self.rc * scale),
            min(1.0, self.gc * scale),
            min(1.0, self.bc * scale),
        )

    def to_hsv(self) -> ColorHSV:
        """Hue + saturation are preserved (ratio-based). V is set to the max ratio by convention."""
        rc, gc, bc = self.rc, self.gc, self.bc
        cmax = max(rc, gc, bc)
        cmin = min(rc, gc, bc)
        delta = cmax - cmin
        if delta == 0:
            h = 0.0
        elif cmax == rc:
            h = (60.0 * ((gc - bc) / delta)) % 360
        elif cmax == gc:
            h = 60.0 * ((bc - rc) / delta) + 120
        else:
            h = 60.0 * ((rc - gc) / delta) + 240
        s = 0.0 if cmax == 0 else delta / cmax
        return ColorHSV(h, s, min(1.0, cmax))


class ColorHex:
    """A single packed 0xRRGGBB integer. Useful for logs, config, human-facing output."""

    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        if not (0 <= value <= 0xFFFFFF):
            raise ValueError(f"ColorHex value must be 0..0xFFFFFF, got 0x{value:X}")
        self.value = value

    def __repr__(self) -> str:
        return f"ColorHex(#{self.value:06X})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ColorHex) and self.value == other.value

    @property
    def r8(self) -> int:
        return (self.value >> 16) & 0xFF

    @property
    def g8(self) -> int:
        return (self.value >> 8) & 0xFF

    @property
    def b8(self) -> int:
        return self.value & 0xFF

    def to_rgb(self) -> ColorRGB:
        return ColorRGB(self.r8 / 255.0, self.g8 / 255.0, self.b8 / 255.0)

    def to_hsv(self) -> ColorHSV:
        return self.to_rgb().to_hsv()


# ── Composite Color (multi-repr, lazy) ────────────────────────────────────

class Color:
    """A single color carrying every representation, derived lazily.

    One rep is the "source" (the one passed to the factory). Any other rep is
    computed and cached on first property read. Use the factory ``from_*``
    methods rather than the raw constructor.

    ``name`` is optional — reference colors in a palette carry a human label
    ("Yellow", "Blue"); measurements coming off a sensor typically do not.
    """

    __slots__ = ("name", "_rgbc", "_rgb", "_hsv", "_chroma", "_hex")

    def __init__(
        self,
        *,
        rgbc: ColorRGBC | None = None,
        rgb: ColorRGB | None = None,
        hsv: ColorHSV | None = None,
        chroma: ColorChroma | None = None,
        hex_: ColorHex | None = None,
        name: str | None = None,
    ) -> None:
        if all(x is None for x in (rgbc, rgb, hsv, chroma, hex_)):
            raise ValueError("Color needs at least one representation as a source")
        self.name = name
        self._rgbc = rgbc
        self._rgb = rgb
        self._hsv = hsv
        self._chroma = chroma
        self._hex = hex_

    # ── Factories ────────────────────────────────────────────────────────
    @classmethod
    def from_rgbc(
        cls,
        r: int,
        g: int,
        b: int,
        c: int,
        full_scale: int = 65535,
        *,
        name: str | None = None,
    ) -> "Color":
        return cls(rgbc=ColorRGBC(r, g, b, c, full_scale), name=name)

    @classmethod
    def from_rgb(cls, r: float, g: float, b: float, *, name: str | None = None) -> "Color":
        return cls(rgb=ColorRGB(r, g, b), name=name)

    @classmethod
    def from_hsv(cls, h: float, s: float, v: float, *, name: str | None = None) -> "Color":
        return cls(hsv=ColorHSV(h, s, v), name=name)

    @classmethod
    def from_chroma(cls, rc: float, gc: float, bc: float, *, name: str | None = None) -> "Color":
        return cls(chroma=ColorChroma(rc, gc, bc), name=name)

    @classmethod
    def from_hex(cls, value: int, *, name: str | None = None) -> "Color":
        return cls(hex_=ColorHex(value), name=name)

    # ── Lazy derived properties ──────────────────────────────────────────
    @property
    def rgbc(self) -> ColorRGBC:
        if self._rgbc is None:
            # No direct RGBC source; derive from RGB at the display full-scale (255).
            # Callers that need sensor-scale RGBC should construct via from_rgbc.
            self._rgbc = self.rgb.to_rgbc()
        return self._rgbc

    @property
    def rgb(self) -> ColorRGB:
        if self._rgb is None:
            if self._rgbc is not None:
                self._rgb = self._rgbc.to_rgb()
            elif self._hsv is not None:
                self._rgb = self._hsv.to_rgb()
            elif self._hex is not None:
                self._rgb = self._hex.to_rgb()
            else:
                assert self._chroma is not None
                self._rgb = self._chroma.to_rgb()
        return self._rgb

    @property
    def hsv(self) -> ColorHSV:
        if self._hsv is None:
            # Prefer sources that already carry intensity info to avoid invented V.
            if self._rgbc is not None:
                self._hsv = self._rgbc.to_hsv()
            elif self._chroma is not None:
                self._hsv = self._chroma.to_hsv()
            else:
                self._hsv = self.rgb.to_hsv()
        return self._hsv

    @property
    def chroma(self) -> ColorChroma:
        if self._chroma is None:
            if self._rgbc is not None:
                self._chroma = self._rgbc.to_chroma()
            else:
                self._chroma = self.rgb.to_chroma()
        return self._chroma

    @property
    def hex(self) -> ColorHex:
        if self._hex is None:
            self._hex = self.rgb.to_hex()
        return self._hex

    def __repr__(self) -> str:
        tag = f"'{self.name}' " if self.name else ""
        return f"Color({tag}{self.hex})"


# ── Named palette keys ────────────────────────────────────────────────────

class NamedColor(IntEnum):
    """Hardcoded palette labels used by sensor classification."""

    Unknown = 0
    Black = 1
    White = 2
    Red = 3
    Green = 4
    Blue = 5
    Yellow = 6


# ── Pure mathematical references ──────────────────────────────────────────

# Fallback palette of mathematically pure primaries/secondaries — used when no
# in-situ calibration is available. These are theoretical colors (100% saturation,
# 100% value in HSV), not empirical sensor readings. For competition-grade
# classification, replace with chip-specific references via a driver-level
# palette (e.g. TCS34725_DEFAULT_PALETTE) or calibrate in-situ.

PURE_COLORS: dict[NamedColor, Color] = {
    NamedColor.Black:  Color.from_hex(0x000000, name="Black"),
    NamedColor.White:  Color.from_hex(0xFFFFFF, name="White"),
    NamedColor.Red:    Color.from_hex(0xFF0000, name="Red"),
    NamedColor.Green:  Color.from_hex(0x00FF00, name="Green"),
    NamedColor.Blue:   Color.from_hex(0x0000FF, name="Blue"),
    NamedColor.Yellow: Color.from_hex(0xFFFF00, name="Yellow"),
}


# ── Palette: classification against named references ─────────────────────

def _hue_distance(h1: float, h2: float) -> float:
    """Shortest angular distance between two hues in degrees, always in [0, 180]."""
    d = abs(h1 - h2) % 360.0
    return d if d <= 180.0 else 360.0 - d


class Palette:
    """Mutable mapping ``NamedColor → Color`` with multi-method classification.

    ``classify`` picks the closest reference in the chosen metric space:

    - ``"hsv"``    — angular distance on Hue, with a saturation floor.
                     Default: robust to illuminant intensity; partly robust to spectral
                     shifts (hue decalibrates a few degrees, not tens).
    - ``"chroma"`` — euclidean distance on r/c, g/c, b/c ratios.
                     Invariant to pure intensity, still sensitive to spectral shifts.
                     Use when the sensor's Clear channel is reliable.
    - ``"rgbc"``   — euclidean distance on raw RGBC ADC counts.
                     Intensity-dependent: legacy behavior, mostly for offline comparison.
    """

    def __init__(
        self,
        refs: dict[NamedColor, Color] | None = None,
        min_saturation: float = 0.15,
        default_method: str = "hsv",
    ) -> None:
        self._refs: dict[NamedColor, Color] = dict(refs) if refs else {}
        self.min_saturation = min_saturation
        self.default_method = default_method

    def set(self, name: NamedColor, ref: Color) -> None:
        self._refs[name] = ref

    def get(self, name: NamedColor) -> Color | None:
        return self._refs.get(name)

    def names(self) -> list[NamedColor]:
        return [n for n in self._refs if n is not NamedColor.Unknown]

    def classify(
        self,
        measured: Color,
        method: str | None = None,
        max_distance: float | None = None,
    ) -> NamedColor:
        """Return the closest ``NamedColor``, or ``NamedColor.Unknown`` if no ref fits.

        ``max_distance`` is expressed in the native unit of ``method``:
        degrees for hue (typical: 30-60), euclidean chroma delta for "chroma"
        (typical: 0.3-0.5), squared RGBC counts for "rgbc" (typical ~1e8).
        """
        if not self._refs:
            return NamedColor.Unknown
        m = method if method is not None else self.default_method

        if m == "hsv":
            return self._classify_hsv(measured, max_distance)
        if m == "chroma":
            return self._classify_chroma(measured, max_distance)
        if m == "rgbc":
            return self._classify_rgbc(measured, max_distance)
        raise ValueError(f"classify method must be 'hsv', 'chroma' or 'rgbc', got {m!r}")

    def _classify_hsv(
        self, measured: Color, max_distance: float | None
    ) -> NamedColor:
        hsv = measured.hsv
        if hsv.s < self.min_saturation:
            return NamedColor.Unknown
        best_name = NamedColor.Unknown
        best_dist = float("inf")
        for name, ref in self._refs.items():
            if name is NamedColor.Unknown:
                continue
            d = _hue_distance(hsv.h, ref.hsv.h)
            if d < best_dist:
                best_dist = d
                best_name = name
        if max_distance is not None and best_dist > max_distance:
            return NamedColor.Unknown
        return best_name

    def _classify_chroma(
        self, measured: Color, max_distance: float | None
    ) -> NamedColor:
        ch = measured.chroma
        best_name = NamedColor.Unknown
        best_dist_sq = float("inf")
        for name, ref in self._refs.items():
            if name is NamedColor.Unknown:
                continue
            rc = ref.chroma
            dr = ch.rc - rc.rc
            dg = ch.gc - rc.gc
            db = ch.bc - rc.bc
            # Squared distance: monotone with euclidean, sqrt skipped (cheap win).
            d = dr * dr + dg * dg + db * db
            if d < best_dist_sq:
                best_dist_sq = d
                best_name = name
        if max_distance is not None and best_dist_sq > max_distance * max_distance:
            return NamedColor.Unknown
        return best_name

    def _classify_rgbc(
        self, measured: Color, max_distance: float | None
    ) -> NamedColor:
        rgbc = measured.rgbc
        best_name = NamedColor.Unknown
        best_dist = float("inf")
        for name, ref in self._refs.items():
            if name is NamedColor.Unknown:
                continue
            rref = ref.rgbc
            dr = rgbc.r - rref.r
            dg = rgbc.g - rref.g
            db = rgbc.b - rref.b
            dc = rgbc.c - rref.c
            d = dr * dr + dg * dg + db * db + dc * dc
            if d < best_dist:
                best_dist = d
                best_name = name
        if max_distance is not None and best_dist > max_distance:
            return NamedColor.Unknown
        return best_name
