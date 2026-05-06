"""Servo driver: adapter that wraps a PWM channel into a Servo.

Converts angles and fractions to pulse widths, delegating the actual
signal generation to any PWM implementation (PCA9685, software PWM, virtual).
"""

import math
from threading import Lock

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.pwm import PWM
from evo_lib.interfaces.servo import Servo, ServoAngleUnit
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral
from evo_lib.registry import Registry
from evo_lib.scheduler import Scheduler
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
        scheduler: Scheduler,
        pwm: PWM,
        move_speed: float,  # In degrees per second
        min_pulse_us: float = 500.0,
        max_pulse_us: float = 2500.0,
        angle_range: float = 180.0,
        min_angle: float = 0.0,
        max_angle: float = 180.0,
    ):
        super().__init__(name)
        self._log = logger
        self._scheduler = scheduler
        self._pwm = pwm
        self._move_speed = move_speed
        self._min_pulse_us = min_pulse_us
        self._max_pulse_us = max_pulse_us
        # Mechanical safety limits. Distinct from the electrical range defined
        # by min/max_pulse_us: those calibrate "what pulse = 0°", while
        # min/max_angle bound "which angles are safe to command physically".
        # Default: no tighter clamp than the electrical range.
        self._angle_range = angle_range
        self._min_angle = min_angle
        self._max_angle = max_angle
        # State
        self._current_task: Task | None = None
        self._is_free = False
        self._current_angle = 0.0
        self._target_angle = 0.0
        self._lock = Lock()

    def wait_or_cancel_current_task(self) -> Task[()]:
        """Wait for the current task if it's a free, otherwise cancel and return now."""
        with self._lock:
            if self._current_task is not None:
                if self._is_free:
                    return self._current_task
                self._current_task.cancel()
            return ImmediateResultTask()

    def init(self) -> Task[()]:
        self.free()
        return ImmediateResultTask()

    def close(self) -> None:
        pass

    def _on_move_complete(self) -> None:
        with self._lock:
            self._current_task = None
            self._current_angle = self._target_angle

    def move_to(
        self,
        position: float,
        unit: ServoAngleUnit,
        wait_multiplier: float = 1.0,
        timeout: float | None = None,
    ) -> Task[()]:
        """Set position as a fraction of the full range.

        Clamped first to [0, 1] (electrical range), then the resulting angle
        is clamped to [min_angle, max_angle] (mechanical safety).
        """
        self.wait_or_cancel_current_task().wait()

        if unit == ServoAngleUnit.NATIVE:
            angle = position
        elif unit == ServoAngleUnit.DEGREES:
            angle = position
        elif unit == ServoAngleUnit.FRACTION:
            angle = position / self._angle_range
        elif unit == ServoAngleUnit.RADIANS:
            angle = math.radians(position)
        else:
            raise ValueError(f"Invalid unit: {unit}")

        angle = max(self._min_angle, min(self._max_angle, angle))
        fraction = angle / self._angle_range
        pulse_us = self._min_pulse_us + fraction * (self._max_pulse_us - self._min_pulse_us)

        with self._lock:
            angle_distance_1 = abs(angle - self._current_angle)
            angle_distance_2 = abs(angle - self._target_angle)

            if angle_distance_1 > angle_distance_2:
                angle_distance = angle_distance_1
            else:
                angle_distance = angle_distance_2
                self._current_angle = self._target_angle

            self._target_angle = angle

            wait_duration = angle_distance / self._move_speed

            set_pulse_task = self._pwm.set_pulse_width_us(pulse_us)
            self._is_free = False
            move_task = self._scheduler.delay_task_after(wait_duration)
            self._current_task = move_task
            move_task.on_complete(self._on_move_complete)

        set_pulse_task.wait()

        return move_task

    def _on_free_done(self) -> None:
        with self._lock:
            self._current_task = None

    def free(self) -> Task[()]:
        """Disable PWM output (servo goes limp)."""
        self._is_free = True
        free_task = self._pwm.free()
        self._current_task = free_task
        free_task.on_done(self._on_free_done)
        return free_task

    @commands.register(
        args=[],
        result=[("angle", ArgTypes.F32(help="Current angle in degrees"))],
    )
    def get_angle(self) -> Task[float]:
        return ImmediateResultTask(self._current_angle)

    @commands.register(
        args=[],
        result=[
            ("enabled", ArgTypes.Bool(help="True if the servo is actively driving a position"))
        ],
    )
    def is_enabled(self) -> Task[bool]:
        # A servo is "enabled" when it has a non-zero pulse commanded, i.e. when
        # it is actively holding a position. free() zeroes the pulse, so this
        # naturally flips to False without any extra state tracking.
        return ImmediateResultTask(not self._is_free)


class PWMServoDefinition(DriverDefinition):
    """Factory for PWMServo from config args. PWM channel resolved by name."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral], scheduler: Scheduler):
        super().__init__(PWMServo.commands)
        self._logger = logger
        self._peripherals = peripherals
        self._scheduler = scheduler

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("pwm", ArgTypes.Component(PWM, self._peripherals))
        defn.add_required("move_speed", ArgTypes.F32())
        defn.add_optional("min_pulse_us", ArgTypes.F32(), 500.0)
        defn.add_optional("max_pulse_us", ArgTypes.F32(), 2500.0)
        defn.add_optional("min_angle", ArgTypes.F32(), 0.0)
        # Sentinel -1 means "unset, default to angle_range". ArgTypes.F32 has
        # no natural "None" default so we use a negative value which is
        # guaranteed to be below any valid servo angle.
        defn.add_optional("max_angle", ArgTypes.F32(), -1.0)
        return defn

    def create(self, args: DriverInitArgs) -> PWMServo:
        return PWMServo(
            name=args.get_name(),
            logger=self._logger,
            scheduler=self._scheduler,
            pwm=args.get("pwm"),
            move_speed=args.get("move_speed"),
            min_pulse_us=args.get("min_pulse_us"),
            max_pulse_us=args.get("max_pulse_us"),
            min_angle=args.get("min_angle"),
            max_angle=args.get("max_angle"),
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


class PWMServoVirtualDefinition(PWMServoDefinition):
    """Factory for PWMServoVirtual from config args."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral], scheduler: Scheduler):
        super().__init__(logger, peripherals, scheduler)
        self.add_commands(PWMServoVirtual.commands)

    def create(self, args: DriverInitArgs) -> PWMServoVirtual:
        return PWMServoVirtual(
            name=args.get_name(),
            logger=self._logger,
            scheduler=self._scheduler,
            pwm=args.get("pwm"),
            move_speed=args.get("move_speed"),
            min_pulse_us=args.get("min_pulse_us"),
            max_pulse_us=args.get("max_pulse_us"),
            min_angle=args.get("min_angle"),
            max_angle=args.get("max_angle"),
        )
