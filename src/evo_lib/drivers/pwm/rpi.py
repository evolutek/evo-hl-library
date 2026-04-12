"""PWM driver: Raspberry Pi hardware PWM via Linux sysfs.

The RPi has 2 hardware PWM channels exposed at /sys/class/pwm/pwmchip0/:
- Channel 0: GPIO 12 or 18
- Channel 1: GPIO 13 or 19

The GPIO pin must be set to ALT function first (via dtoverlay in config.txt).
This driver writes period/duty_cycle in nanoseconds to sysfs files.
"""

from pathlib import Path

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.drivers.pwm.virtual import PWMVirtual
from evo_lib.interfaces.pwm import PWM
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task

_DEFAULT_CHIP = "/sys/class/pwm/pwmchip0"


class RpiPWM(PWM):
    """Hardware PWM on Raspberry Pi via sysfs."""

    def __init__(
        self,
        name: str,
        logger: Logger,
        channel: int,
        freq_hz: float = 50.0,
        chip_path: str = _DEFAULT_CHIP,
    ):
        super().__init__(name)
        if channel not in (0, 1):
            raise ValueError(f"RPi PWM channel must be 0 or 1, got {channel}")
        self._log = logger
        self._channel = channel
        self._freq_hz = freq_hz
        self._period_ns = round(1_000_000_000 / freq_hz)
        self._path = Path(chip_path) / f"pwm{channel}"
        self._chip_path = Path(chip_path)
        self._exported = False
        self._initialized = False

    def _check_init(self) -> None:
        if not self._initialized:
            raise RuntimeError("PWM not initialized, call init() first")

    def init(self) -> Task[()]:
        # Export the channel if not already present
        if not self._path.exists():
            (self._chip_path / "export").write_text(str(self._channel))
            self._exported = True
        # Set period (frequency)
        (self._path / "period").write_text(str(self._period_ns))
        # Start with output disabled
        (self._path / "duty_cycle").write_text("0")
        (self._path / "enable").write_text("1")
        self._initialized = True
        self._log.info(
            f"RpiPWM '{self.name}' initialized on channel {self._channel}, "
            f"freq={self._freq_hz:.1f} Hz"
        )
        return ImmediateResultTask()

    def close(self) -> None:
        if not self._initialized:
            return
        self._initialized = False
        if self._path.exists():
            (self._path / "enable").write_text("0")
            if self._exported:
                (self._chip_path / "unexport").write_text(str(self._channel))
                self._exported = False
        self._log.info(f"RpiPWM '{self.name}' closed")

    def set_duty_cycle(self, duty: float) -> Task[()]:
        self._check_init()
        duty = max(0.0, min(1.0, duty))
        duty_ns = round(duty * self._period_ns)
        (self._path / "duty_cycle").write_text(str(duty_ns))
        return ImmediateResultTask(None)

    def set_pulse_width_us(self, width_us: float) -> Task[()]:
        self._check_init()
        duty_ns = round(width_us * 1000)
        duty_ns = max(0, min(self._period_ns, duty_ns))
        (self._path / "duty_cycle").write_text(str(duty_ns))
        return ImmediateResultTask(None)

    def free(self) -> Task[()]:
        self._check_init()
        (self._path / "duty_cycle").write_text("0")
        return ImmediateResultTask(None)


class RpiPWMDefinition(DriverDefinition):
    """Factory for RpiPWM from config args."""

    def __init__(self, logger: Logger):
        super().__init__(RpiPWM.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("channel", ArgTypes.U8())
        defn.add_optional("freq_hz", ArgTypes.F32(), 50.0)
        defn.add_optional("chip_path", ArgTypes.String(), _DEFAULT_CHIP)
        return defn

    def create(self, args: DriverInitArgs) -> RpiPWM:
        return RpiPWM(
            name=args.get_name(),
            logger=self._logger,
            channel=args.get("channel"),
            freq_hz=args.get("freq_hz"),
            chip_path=args.get("chip_path"),
        )


class RpiPWMVirtual(PWMVirtual):
    """Virtual twin of RpiPWM: same constructor signature, pure in-memory.

    Accepts the same (name, logger, channel, freq_hz, chip_path) signature
    as RpiPWM so the factory can swap them transparently in config. Channel
    and chip_path are stored for introspection but no sysfs I/O happens.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        channel: int,
        freq_hz: float = 50.0,
        chip_path: str = _DEFAULT_CHIP,
    ):
        super().__init__(name, logger, freq_hz)
        if channel not in (0, 1):
            raise ValueError(f"RPi PWM channel must be 0 or 1, got {channel}")
        self._channel = channel
        self._chip_path = chip_path


class RpiPWMVirtualDefinition(DriverDefinition):
    """Factory for RpiPWMVirtual from config args."""

    def __init__(self, logger: Logger):
        super().__init__(RpiPWMVirtual.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("channel", ArgTypes.U8())
        defn.add_optional("freq_hz", ArgTypes.F32(), 50.0)
        defn.add_optional("chip_path", ArgTypes.String(), _DEFAULT_CHIP)
        return defn

    def create(self, args: DriverInitArgs) -> RpiPWMVirtual:
        return RpiPWMVirtual(
            name=args.get_name(),
            logger=self._logger,
            channel=args.get("channel"),
            freq_hz=args.get("freq_hz"),
            chip_path=args.get("chip_path"),
        )
