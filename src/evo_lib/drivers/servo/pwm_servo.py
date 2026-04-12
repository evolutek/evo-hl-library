"""Servo driver: adapter that wraps a PWM channel into a Servo.

Converts angles and fractions to pulse widths, delegating the actual
signal generation to any PWM implementation (PCA9685, software PWM, virtual).
"""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.pwm import PWM
from evo_lib.interfaces.servo import Servo
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task


class PWMServo(Servo):
    """Turns a PWM output into an angle-controlled servo.

    The conversion is linear: angle 0 maps to min_pulse_us,
    angle angle_range maps to max_pulse_us.

    Read-back commands (`get_angle`, `get_fraction`, `is_enabled`) derive
    their answer from the underlying PWM's last commanded pulse width, so
    they require the PWM implementation to expose `get_pulse_width_us`.
    """

    commands = DriverCommands(parents=[Servo.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        pwm: PWM,
        min_pulse_us: float = 500.0,
        max_pulse_us: float = 2500.0,
        angle_range: float = 180.0,
        min_angle: float = 0.0,
        max_angle: float | None = None,
    ):
        super().__init__(name)
        self._log = logger
        self._pwm = pwm
        self._min_pulse_us = min_pulse_us
        self._max_pulse_us = max_pulse_us
        self._angle_range = angle_range
        # Mechanical safety limits. Distinct from the electrical range defined
        # by min/max_pulse_us: those calibrate "what pulse = 0°", while
        # min/max_angle bound "which angles are safe to command physically".
        # Default: no tighter clamp than the electrical range.
        self._min_angle = min_angle
        self._max_angle = angle_range if max_angle is None else max_angle

    def init(self) -> Task[()]:
        return ImmediateResultTask()

    def close(self) -> None:
        pass

    def move_to_angle(self, angle: float) -> Task[()]:
        """Move to the given angle. Clamped to [min_angle, max_angle]."""
        return self.move_to_fraction(angle / self._angle_range)

    def move_to_fraction(self, fraction: float) -> Task[()]:
        """Set position as a fraction of the full range.

        Clamped first to [0, 1] (electrical range), then the resulting angle
        is clamped to [min_angle, max_angle] (mechanical safety).
        """
        fraction = max(0.0, min(1.0, fraction))
        angle = fraction * self._angle_range
        angle = max(self._min_angle, min(self._max_angle, angle))
        fraction = angle / self._angle_range
        pulse_us = self._min_pulse_us + fraction * (self._max_pulse_us - self._min_pulse_us)
        return self._pwm.set_pulse_width_us(pulse_us)

    def free(self) -> Task[()]:
        """Disable PWM output (servo goes limp)."""
        return self._pwm.free()

    def _read_pulse_us(self) -> float:
        (pulse_us,) = self._pwm.get_pulse_width_us().wait()
        return pulse_us

    @commands.register(
        args=[],
        result=[("angle", ArgTypes.F32(help="Current angle in degrees"))],
    )
    def get_angle(self) -> Task[float]:
        pulse_us = self._read_pulse_us()
        fraction = (pulse_us - self._min_pulse_us) / (self._max_pulse_us - self._min_pulse_us)
        return ImmediateResultTask(fraction * self._angle_range)

    @commands.register(
        args=[],
        result=[("fraction", ArgTypes.F32(help="Current position as fraction of full range"))],
    )
    def get_fraction(self) -> Task[float]:
        pulse_us = self._read_pulse_us()
        return ImmediateResultTask(
            (pulse_us - self._min_pulse_us) / (self._max_pulse_us - self._min_pulse_us)
        )

    @commands.register(
        args=[],
        result=[("enabled", ArgTypes.Bool(help="True if the servo is actively driving a position"))],
    )
    def is_enabled(self) -> Task[bool]:
        # A servo is "enabled" when it has a non-zero pulse commanded, i.e. when
        # it is actively holding a position. free() zeroes the pulse, so this
        # naturally flips to False without any extra state tracking.
        return ImmediateResultTask(self._read_pulse_us() > 0.0)


class PWMServoDefinition(DriverDefinition):
    """Factory for PWMServo from config args. PWM channel resolved by name."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(PWMServo.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("pwm", ArgTypes.Component(PWM, self._peripherals))
        defn.add_optional("min_pulse_us", ArgTypes.F32(), 500.0)
        defn.add_optional("max_pulse_us", ArgTypes.F32(), 2500.0)
        defn.add_optional("angle_range", ArgTypes.F32(), 180.0)
        defn.add_optional("min_angle", ArgTypes.F32(), 0.0)
        # Sentinel -1 means "unset, default to angle_range". ArgTypes.F32 has
        # no natural "None" default so we use a negative value which is
        # guaranteed to be below any valid servo angle.
        defn.add_optional("max_angle", ArgTypes.F32(), -1.0)
        return defn

    def create(self, args: DriverInitArgs) -> PWMServo:
        max_angle_raw = args.get("max_angle")
        max_angle = None if max_angle_raw < 0 else max_angle_raw
        return PWMServo(
            name=args.get_name(),
            logger=self._logger,
            pwm=args.get("pwm"),
            min_pulse_us=args.get("min_pulse_us"),
            max_pulse_us=args.get("max_pulse_us"),
            angle_range=args.get("angle_range"),
            min_angle=args.get("min_angle"),
            max_angle=max_angle,
        )


class PWMServoVirtual(PWMServo):
    """Drop-in twin of PWMServo for the `virtual_pwm_servo` registry slot.

    Currently has no extra behaviour — PWMServo itself now hosts the read-back
    commands, and the virtual-ness comes entirely from the injected PWM being
    a PWMVirtual. Kept as a distinct class so that future debug/simulation
    hooks (injected faults, latency, snapshots) have a natural place to live
    without touching the real driver.
    """

    commands = DriverCommands(parents=[PWMServo.commands])


class PWMServoVirtualDefinition(DriverDefinition):
    """Factory for PWMServoVirtual from config args."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(PWMServoVirtual.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("pwm", ArgTypes.Component(PWM, self._peripherals))
        defn.add_optional("min_pulse_us", ArgTypes.F32(), 500.0)
        defn.add_optional("max_pulse_us", ArgTypes.F32(), 2500.0)
        defn.add_optional("angle_range", ArgTypes.F32(), 180.0)
        defn.add_optional("min_angle", ArgTypes.F32(), 0.0)
        defn.add_optional("max_angle", ArgTypes.F32(), -1.0)  # -1 = default to angle_range
        return defn

    def create(self, args: DriverInitArgs) -> PWMServoVirtual:
        max_angle_raw = args.get("max_angle")
        max_angle = None if max_angle_raw < 0 else max_angle_raw
        return PWMServoVirtual(
            name=args.get_name(),
            logger=self._logger,
            pwm=args.get("pwm"),
            min_pulse_us=args.get("min_pulse_us"),
            max_pulse_us=args.get("max_pulse_us"),
            angle_range=args.get("angle_range"),
            min_angle=args.get("min_angle"),
            max_angle=max_angle,
        )
