"""TCS34725 RGBC color sensor over I2C, with optional on-board LED.

The driver implements two features that matter for noisy / variable lighting:

1. **Flash differential** — ``read_color`` reads twice (LED OFF, LED ON) and
   returns the per-channel difference, effectively subtracting ambient light.
   Useful under TV projectors or changing table lighting. Disable via
   ``use_flash_differential=False`` for debug, benchmarks, or when no LED
   is wired.
2. **Auto-exposure** — ``auto_expose`` iteratively adjusts integration time
   to keep the Clear channel mid-range, avoiding saturation and keeping the
   sensor in its linear regime.

Classification is delegated to a ``Palette`` (default method: ``"hsv"``
— hue is the most illuminant-robust of the available metrics).
"""

import struct
import threading
import time

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.color_sensor import ColorSensor
from evo_lib.interfaces.i2c import I2C
from evo_lib.interfaces.led import LED
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral
from evo_lib.registry import Registry
from evo_lib.task import DelayedTask, ImmediateResultTask, Task
from evo_lib.types.color import Color, ColorRGBC, NamedColor, Palette

_COMMAND_BIT = 0x80

_ENABLE = 0x00
_ATIME = 0x01
_CONTROL = 0x0F
_STATUS = 0x13
_CDATA = 0x14

_ENABLE_PON = 0x01
_ENABLE_AEN = 0x02
_STATUS_AVALID = 0x01

_GAIN_TO_BYTE = {1: 0x00, 4: 0x01, 16: 0x02, 60: 0x03}

_ATIME_STEP_MS = 2.4
_ATIME_DEFAULT = 0xD5

# Datasheet §Principles of Operation, Figure 9: 2.4 ms warm-up after PON.
_POWER_ON_DELAY_S = 0.0024

# Auto-exposure defaults: aim for the middle of the linear range.
# ~45% of the theoretical 65535 max: enough headroom against saturation,
# still well above the sensor noise floor.
_AUTO_EXPOSE_TARGET_C = 30000
_AUTO_EXPOSE_TOLERANCE = 0.2
_AUTO_EXPOSE_MAX_ITER = 5


def _ms_to_atime(ms: float) -> int:
    return max(0, min(255, round(256 - ms / _ATIME_STEP_MS)))


def _atime_to_ms(atime: int) -> float:
    return (256 - atime) * _ATIME_STEP_MS


# Indicative refs for AGAIN=4×, ATIME≈100 ms, lit by the on-board white LED.
# Refine per-instance via calibrate() if responsivity drifts too much.
TCS34725_DEFAULT_PALETTE: dict[NamedColor, Color] = {
    NamedColor.Black:  Color.from_rgbc(   200,   200,   200,    600, name="Black"),
    NamedColor.White:  Color.from_rgbc( 15000, 15000, 15000,  45000, name="White"),
    NamedColor.Red:    Color.from_rgbc(  8500,  1200,   800,  10500, name="Red"),
    NamedColor.Green:  Color.from_rgbc(  1100,  6200,  1400,   8700, name="Green"),
    NamedColor.Blue:   Color.from_rgbc(   800,  1400,  5500,   7700, name="Blue"),
    NamedColor.Yellow: Color.from_rgbc(  7000,  6500,  1500,  15000, name="Yellow"),
}


class TCS34725(ColorSensor):
    commands = DriverCommands(parents=[ColorSensor.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        bus: I2C,
        address: int = 0x29,
        integration_time_ms: float = _atime_to_ms(_ATIME_DEFAULT),
        gain: int = 4,
        light: LED | None = None,
        palette: Palette | None = None,
        use_flash_differential: bool = True,
    ):
        super().__init__(name)
        if gain not in _GAIN_TO_BYTE:
            raise ValueError(f"gain must be 1/4/16/60, got {gain}")
        self._log = logger
        self._bus = bus
        self._address = address
        self._atime = _ms_to_atime(integration_time_ms)
        self._gain = gain
        self._light = light
        self._palette = palette if palette is not None else Palette(refs=TCS34725_DEFAULT_PALETTE)
        # Flash differential needs a wired LED — silently disable otherwise.
        self._use_flash_differential = use_flash_differential and (light is not None)
        self._lock = threading.Lock()

    def init(self) -> Task[()]:
        self._write_register(_ENABLE, _ENABLE_PON)
        task: DelayedTask[()] = DelayedTask()

        def finish_init() -> None:
            try:
                self._write_register(_ENABLE, _ENABLE_PON | _ENABLE_AEN)
                self._write_register(_ATIME, self._atime)
                self._write_register(_CONTROL, _GAIN_TO_BYTE[self._gain])
                flash = "ON" if self._use_flash_differential else "OFF"
                self._log.info(
                    f"TCS34725 '{self.name}' initialized at 0x{self._address:02x} "
                    f"(integration={_atime_to_ms(self._atime):.1f}ms, gain={self._gain}x, flash={flash})"
                )
                task.complete()
            except Exception as exc:
                task.error(exc)

        threading.Timer(_POWER_ON_DELAY_S, finish_init).start()
        return task

    def get_full_scale(self) -> int:
        """Max possible ADC count for the current ATIME."""
        return min(65535, (256 - self._atime) * 1024)

    def close(self) -> None:
        self._write_register(_ENABLE, 0x00)

    def read_color(self) -> Task[ColorRGBC]:
        """Return one RGBC measurement. Flash-differential if enabled and LED wired.

        Flash-differential sequence:

        - Read with LED OFF → ``off`` (captures ambient only)
        - Read with LED ON  → ``on``  (captures ambient + LED)
        - Return ``on − off`` per channel, clamped ≥ 0.

        The returned signal depends only on the LED and the pad's reflectance —
        ambient illumination cancels out, even under TV projector lighting.
        """
        if not self._use_flash_differential or self._light is None:
            return ImmediateResultTask(self._read_raw_blocking())

        (original_intensity,) = self._light.get_intensity().wait()
        try:
            self._light.set_intensity(0.0).wait()
            self._wait_fresh_integration()
            off = self._read_raw_blocking()

            self._light.set_intensity(1.0).wait()
            self._wait_fresh_integration()
            on = self._read_raw_blocking()
        finally:
            self._light.set_intensity(original_intensity).wait()

        diff = ColorRGBC(
            r=max(0, on.r - off.r),
            g=max(0, on.g - off.g),
            b=max(0, on.b - off.b),
            c=max(0, on.c - off.c),
            full_scale=on.full_scale,
        )
        return ImmediateResultTask(diff)

    def get_color(self) -> Task[NamedColor]:
        (raw,) = self.read_color().wait()
        return ImmediateResultTask(self._palette.classify(Color(rgbc=raw)))

    def calibrate(self, name: NamedColor, samples: int = 10) -> Task[()]:
        """Average ``samples`` live readings and store the result as the palette ref for ``name``.

        Each sample goes through ``read_color``, so flash-differential applies when enabled.
        """
        if samples < 1:
            raise ValueError(f"samples must be >= 1, got {samples}")
        sr = sg = sb = sc = 0
        fs = 65535
        for _ in range(samples):
            (raw,) = self.read_color().wait()
            sr += raw.r
            sg += raw.g
            sb += raw.b
            sc += raw.c
            fs = raw.full_scale
        avg = ColorRGBC(
            r=sr // samples,
            g=sg // samples,
            b=sb // samples,
            c=sc // samples,
            full_scale=fs,
        )
        self._palette.set(name, Color(rgbc=avg, name=name.name))
        self._log.info(
            f"TCS34725 '{self.name}' calibrated {name.name}: "
            f"r={avg.r} g={avg.g} b={avg.b} c={avg.c}"
        )
        return ImmediateResultTask()

    @commands.register(
        args=[
            ("target_c", ArgTypes.U16(help="Target Clear channel level (default ~30000)")),
        ],
        result=[],
    )
    def auto_expose(
        self,
        target_c: int = _AUTO_EXPOSE_TARGET_C,
        tolerance: float = _AUTO_EXPOSE_TOLERANCE,
        max_iterations: int = _AUTO_EXPOSE_MAX_ITER,
    ) -> Task[()]:
        """Iteratively tune ATIME to center the Clear channel on ``target_c``.

        Converges when the measured C is within ``tolerance`` of target, or
        after ``max_iterations`` passes. Skips gain changes — ATIME alone
        covers a ~250× dynamic range (3 ms → 614 ms), enough for table lighting.
        """
        for _ in range(max_iterations):
            raw = self._read_raw_blocking()
            c = max(1, raw.c)
            ratio = target_c / c
            if abs(ratio - 1.0) < tolerance:
                break
            new_ms = _atime_to_ms(self._atime) * ratio
            new_ms = max(3.0, min(600.0, new_ms))
            self._atime = _ms_to_atime(new_ms)
            self._write_register(_ATIME, self._atime)
            self._wait_fresh_integration()
        self._log.info(
            f"TCS34725 '{self.name}' auto_expose: integration={_atime_to_ms(self._atime):.1f}ms"
        )
        return ImmediateResultTask()

    def set_light(self, intensity: float) -> Task[()]:
        if self._light is None:
            return ImmediateResultTask()
        return self._light.set_intensity(intensity)

    def get_light(self) -> Task[float]:
        if self._light is None:
            return ImmediateResultTask(0.0)
        return self._light.get_intensity()

    def set_gamma(self, gamma: float) -> Task[()]:
        # Palette classification runs in HSV/Chroma by default, both ratio-based
        # and thus independent of display gamma. Kept as interface shim.
        return ImmediateResultTask()

    def get_gamma(self) -> Task[float]:
        return ImmediateResultTask(1.0)

    @commands.register(
        args=[("gain", ArgTypes.U8(help="Analog gain: 1, 4, 16 or 60"))],
        result=[],
    )
    def set_gain(self, gain: int) -> Task[()]:
        if gain not in _GAIN_TO_BYTE:
            raise ValueError(f"gain must be 1/4/16/60, got {gain}")
        self._gain = gain
        self._write_register(_CONTROL, _GAIN_TO_BYTE[gain])
        return ImmediateResultTask()

    @commands.register(
        args=[],
        result=[("gain", ArgTypes.U8(help="Current analog gain multiplier"))],
    )
    def get_gain(self) -> Task[int]:
        return ImmediateResultTask(self._gain)

    @commands.register(
        args=[("ms", ArgTypes.F32(help="Integration time in ms (2.4-614)"))],
        result=[],
    )
    def set_integration_time(self, ms: float) -> Task[()]:
        self._atime = _ms_to_atime(ms)
        self._write_register(_ATIME, self._atime)
        return ImmediateResultTask()

    @commands.register(
        args=[],
        result=[("ms", ArgTypes.F32(help="Current integration time (ms)"))],
    )
    def get_integration_time(self) -> Task[float]:
        return ImmediateResultTask(_atime_to_ms(self._atime))

    @commands.register(
        args=[("enabled", ArgTypes.Bool(help="True to enable LED ON/OFF subtraction"))],
        result=[],
    )
    def set_flash_differential(self, enabled: bool) -> Task[()]:
        self._use_flash_differential = enabled and (self._light is not None)
        return ImmediateResultTask()

    @commands.register(
        args=[],
        result=[("enabled", ArgTypes.Bool(help="Flash-differential subtraction state"))],
    )
    def get_flash_differential(self) -> Task[bool]:
        return ImmediateResultTask(self._use_flash_differential)

    # ── Internal helpers ─────────────────────────────────────────────────

    def _read_raw_blocking(self) -> ColorRGBC:
        self._wait_data_ready()
        with self._lock:
            (data,) = self._bus.write_then_read(
                self._address, bytes([_COMMAND_BIT | _CDATA]), 8
            ).wait()
        c, r, g, b = struct.unpack("<HHHH", data)
        return ColorRGBC(r=r, g=g, b=b, c=c, full_scale=self.get_full_scale())

    def _wait_fresh_integration(self) -> None:
        """Sleep long enough for a full new integration cycle under the new light state.

        After a light change, the in-progress integration mixes old and new
        illumination. Waiting 1.5 × ATIME ensures the next AVALID reflects
        only the new lighting — a conservative bound that avoids register
        gymnastics with AEN toggling.
        """
        time.sleep(1.5 * _atime_to_ms(self._atime) / 1000.0)

    def _wait_data_ready(self, timeout_s: float = 1.0) -> None:
        deadline = time.monotonic() + timeout_s
        while True:
            if self._read_register(_STATUS) & _STATUS_AVALID:
                return
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"TCS34725 '{self.name}' AVALID not set within {timeout_s}s"
                )
            time.sleep(0.002)

    def _write_register(self, register: int, value: int) -> None:
        with self._lock:
            self._bus.write_to(
                self._address, bytes([_COMMAND_BIT | register, value])
            ).wait()

    def _read_register(self, register: int) -> int:
        with self._lock:
            (data,) = self._bus.write_then_read(
                self._address, bytes([_COMMAND_BIT | register]), 1
            ).wait()
        return data[0]


class TCS34725Definition(DriverDefinition):
    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(TCS34725.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("address", ArgTypes.U8(), 0x29)
        defn.add_optional("integration_time_ms", ArgTypes.F32(), _atime_to_ms(_ATIME_DEFAULT))
        defn.add_optional("gain", ArgTypes.U8(), 4)
        defn.add_optional("light", ArgTypes.OptionalComponent(LED, self._peripherals), None)
        defn.add_optional("use_flash_differential", ArgTypes.Bool(), True)
        return defn

    def create(self, args: DriverInitArgs) -> TCS34725:
        name = args.get_name()
        return TCS34725(
            name=name,
            logger=self._logger.get_sublogger(name),
            bus=args.get("bus"),
            address=args.get("address"),
            integration_time_ms=args.get("integration_time_ms"),
            gain=args.get("gain"),
            light=args.get("light"),
            use_flash_differential=args.get("use_flash_differential"),
        )


class TCS34725Virtual(ColorSensor):
    """Simulation twin of TCS34725 — injected RGBC values, same surface as the real driver."""

    commands = DriverCommands(parents=[ColorSensor.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        initial_r: int = 0,
        initial_g: int = 0,
        initial_b: int = 0,
        initial_c: int = 0,
        light: LED | None = None,
        palette: Palette | None = None,
        use_flash_differential: bool = True,
    ):
        super().__init__(name)
        self._log = logger
        # full_scale pinned at 65535 in simulation — ATIME-dependence is orthogonal
        # to injection and would only complicate test setup.
        self._raw = ColorRGBC(r=initial_r, g=initial_g, b=initial_b, c=initial_c, full_scale=65535)
        self._light = light
        self._palette = palette if palette is not None else Palette(refs=TCS34725_DEFAULT_PALETTE)
        # Kept for signature parity with the real driver — no ambient to subtract
        # in simulation, so it's a no-op on read_color but preserved for round-trip symmetry.
        self._use_flash_differential = use_flash_differential

    def init(self) -> Task[()]:
        self._log.info(f"TCS34725Virtual '{self.name}' initialized")
        return ImmediateResultTask()

    def close(self) -> None:
        pass

    def read_color(self) -> Task[ColorRGBC]:
        return ImmediateResultTask(self._raw)

    def get_color(self) -> Task[NamedColor]:
        return ImmediateResultTask(self._palette.classify(Color(rgbc=self._raw)))

    @commands.register(
        args=[("name", ArgTypes.Enum(NamedColor, help="Named color to simulate"))],
        result=[],
    )
    def set_color(self, name: NamedColor) -> Task[()]:
        """Simulate the sensor perceiving ``name`` by copying its palette ref into the live reading."""
        ref = self._palette.get(name)
        if ref is None:
            raise ValueError(f"palette has no entry for {name.name}")
        self._raw = ref.rgbc
        return ImmediateResultTask()

    @commands.register(
        args=[("name", ArgTypes.Enum(NamedColor, help="Palette entry to populate"))],
        result=[],
    )
    def calibrate(self, name: NamedColor, samples: int = 10) -> Task[()]:
        if samples != 10:
            self._log.debug(
                f"TCS34725Virtual '{self.name}' calibrate: samples={samples} ignored "
                "(virtual reads the injected value directly)"
            )
        self._palette.set(name, Color(rgbc=self._raw, name=name.name))
        return ImmediateResultTask()

    def auto_expose(
        self,
        target_c: int = _AUTO_EXPOSE_TARGET_C,
        tolerance: float = _AUTO_EXPOSE_TOLERANCE,
        max_iterations: int = _AUTO_EXPOSE_MAX_ITER,
    ) -> Task[()]:
        # No exposure to tune in simulation — kept for signature parity.
        return ImmediateResultTask()

    def get_full_scale(self) -> int:
        return 65535

    def set_light(self, intensity: float) -> Task[()]:
        if self._light is None:
            return ImmediateResultTask()
        return self._light.set_intensity(intensity)

    def get_light(self) -> Task[float]:
        if self._light is None:
            return ImmediateResultTask(0.0)
        return self._light.get_intensity()

    def set_gamma(self, gamma: float) -> Task[()]:
        return ImmediateResultTask()

    def get_gamma(self) -> Task[float]:
        return ImmediateResultTask(1.0)

    @commands.register(
        args=[("enabled", ArgTypes.Bool(help="True to enable LED ON/OFF subtraction"))],
        result=[],
    )
    def set_flash_differential(self, enabled: bool) -> Task[()]:
        self._use_flash_differential = enabled
        return ImmediateResultTask()

    @commands.register(
        args=[],
        result=[("enabled", ArgTypes.Bool(help="Flash-differential subtraction state"))],
    )
    def get_flash_differential(self) -> Task[bool]:
        return ImmediateResultTask(self._use_flash_differential)

    @commands.register(
        args=[
            ("r", ArgTypes.U16(help="Red ADC counts to inject")),
            ("g", ArgTypes.U16(help="Green ADC counts to inject")),
            ("b", ArgTypes.U16(help="Blue ADC counts to inject")),
            ("c", ArgTypes.U16(help="Clear ADC counts to inject")),
        ],
        result=[],
    )
    def inject_color(self, r: int, g: int, b: int, c: int) -> Task[()]:
        """Set the raw RGBC values returned by subsequent read_color calls."""
        self._raw = ColorRGBC(r=r, g=g, b=b, c=c, full_scale=65535)
        return ImmediateResultTask()


class TCS34725VirtualDefinition(DriverDefinition):
    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(TCS34725Virtual.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_optional("initial_r", ArgTypes.U16(), 0)
        defn.add_optional("initial_g", ArgTypes.U16(), 0)
        defn.add_optional("initial_b", ArgTypes.U16(), 0)
        defn.add_optional("initial_c", ArgTypes.U16(), 0)
        defn.add_optional("light", ArgTypes.OptionalComponent(LED, self._peripherals), None)
        defn.add_optional("use_flash_differential", ArgTypes.Bool(), True)
        return defn

    def create(self, args: DriverInitArgs) -> TCS34725Virtual:
        name = args.get_name()
        return TCS34725Virtual(
            name=name,
            logger=self._logger.get_sublogger(name),
            initial_r=args.get("initial_r"),
            initial_g=args.get("initial_g"),
            initial_b=args.get("initial_b"),
            initial_c=args.get("initial_c"),
            light=args.get("light"),
            use_flash_differential=args.get("use_flash_differential"),
        )
