"""TCS34725 RGBC color sensor over I2C, with optional on-board LED."""

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
from evo_lib.types.color import ColorRaw, NamedColor, Palette

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
_POWER_ON_DELAY_S = 0.003


def _ms_to_atime(ms: float) -> int:
    return max(0, min(255, round(256 - ms / _ATIME_STEP_MS)))


def _atime_to_ms(atime: int) -> float:
    return (256 - atime) * _ATIME_STEP_MS


# Indicative refs for AGAIN=4×, ATIME≈100 ms, lit by an on-board white LED.
# Refine per-instance via calibrate() if responsivity drifts too much.
TCS34725_DEFAULT_PALETTE: dict[NamedColor, ColorRaw] = {
    NamedColor.Black:  ColorRaw(   200,   200,   200,    600),
    NamedColor.White:  ColorRaw( 15000, 15000, 15000,  45000),
    NamedColor.Red:    ColorRaw(  8500,  1200,   800,  10500),
    NamedColor.Green:  ColorRaw(  1100,  6200,  1400,   8700),
    NamedColor.Blue:   ColorRaw(   800,  1400,  5500,   7700),
    NamedColor.Yellow: ColorRaw(  7000,  6500,  1500,  15000),
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
        unknown_threshold_squared: float | None = None,
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
        self._unknown_threshold_squared = unknown_threshold_squared
        self._lock = threading.Lock()

    def init(self) -> Task[()]:
        self._write_register(_ENABLE, _ENABLE_PON)
        task: DelayedTask[()] = DelayedTask()

        def finish_init() -> None:
            try:
                self._write_register(_ENABLE, _ENABLE_PON | _ENABLE_AEN)
                self._write_register(_ATIME, self._atime)
                self._write_register(_CONTROL, _GAIN_TO_BYTE[self._gain])
                self._log.info(
                    f"TCS34725 '{self.name}' initialized at 0x{self._address:02x} "
                    f"(integration={_atime_to_ms(self._atime):.1f}ms, gain={self._gain}x)"
                )
                task.complete()
            except Exception as exc:
                task.error(exc)

        threading.Timer(_POWER_ON_DELAY_S, finish_init).start()
        return task

    def get_full_scale(self) -> int:
        """Max possible ADC count for the current ATIME; use with ``Color.from_raw``."""
        return min(65535, (256 - self._atime) * 1024)

    def close(self) -> None:
        self._write_register(_ENABLE, 0x00)

    def read_color(self) -> Task[ColorRaw]:
        self._wait_data_ready()
        with self._lock:
            (data,) = self._bus.write_then_read(
                self._address, bytes([_COMMAND_BIT | _CDATA]), 8
            ).wait()
        c, r, g, b = struct.unpack("<HHHH", data)
        return ImmediateResultTask(ColorRaw(r=r, g=g, b=b, c=c))

    def get_color(self) -> Task[NamedColor]:
        (raw,) = self.read_color().wait()
        return ImmediateResultTask(
            self._palette.classify(raw, self._unknown_threshold_squared)
        )

    def set_color(self, name: NamedColor, r: int, g: int, b: int, c: int) -> Task[()]:
        self._palette.set(name, ColorRaw(r=r, g=g, b=b, c=c))
        return ImmediateResultTask()

    def calibrate(self, name: NamedColor, samples: int = 10) -> Task[()]:
        if samples < 1:
            raise ValueError(f"samples must be >= 1, got {samples}")
        sr = sg = sb = sc = 0
        for _ in range(samples):
            (raw,) = self.read_color().wait()
            sr += raw.r
            sg += raw.g
            sb += raw.b
            sc += raw.c
        avg = ColorRaw(r=sr // samples, g=sg // samples,
                       b=sb // samples, c=sc // samples)
        self._palette.set(name, avg)
        self._log.info(
            f"TCS34725 '{self.name}' calibrated {name.name}: "
            f"r={avg.r} g={avg.g} b={avg.b} c={avg.c}"
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
        self._palette.set_gamma(gamma)
        return ImmediateResultTask()

    def get_gamma(self) -> Task[float]:
        return ImmediateResultTask(self._palette.get_gamma())

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
        )


class TCS34725Virtual(ColorSensor):
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
        unknown_threshold_squared: float | None = None,
    ):
        super().__init__(name)
        self._log = logger
        self._raw = ColorRaw(r=initial_r, g=initial_g, b=initial_b, c=initial_c)
        self._light = light
        self._palette = palette if palette is not None else Palette(refs=TCS34725_DEFAULT_PALETTE)
        self._unknown_threshold_squared = unknown_threshold_squared

    def init(self) -> Task[()]:
        self._log.info(f"TCS34725Virtual '{self.name}' initialized")
        return ImmediateResultTask()

    def close(self) -> None:
        pass

    def read_color(self) -> Task[ColorRaw]:
        return ImmediateResultTask(self._raw)

    def get_color(self) -> Task[NamedColor]:
        return ImmediateResultTask(
            self._palette.classify(self._raw, self._unknown_threshold_squared)
        )

    def set_color(self, name: NamedColor, r: int, g: int, b: int, c: int) -> Task[()]:
        self._palette.set(name, ColorRaw(r=r, g=g, b=b, c=c))
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
        self._palette.set(name, self._raw)
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
        self._palette.set_gamma(gamma)
        return ImmediateResultTask()

    def get_gamma(self) -> Task[float]:
        return ImmediateResultTask(self._palette.get_gamma())

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
        self._raw = ColorRaw(r=r, g=g, b=b, c=c)
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
        )
