"""Servo driver: virtual implementation for testing and simulation."""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands, DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.interfaces.servo import Servo
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task


class ServoVirtual(Servo):
    """In-memory servo for tests and simulation.

    Exposes read-back commands (get_angle, get_fraction, is_enabled) on top
    of the real Servo commands so the REPL can observe simulated state.
    """

    commands = DriverCommands(parents=[Servo.commands])

    def __init__(self, name: str, logger: Logger, angle_range: float = 180.0):
        super().__init__(name)
        self._log = logger
        self._angle_range = angle_range
        self.current_angle: float = 0.0
        self.current_fraction: float = 0.0
        self.enabled: bool = False

    def init(self) -> Task[()]:
        self.enabled = True
        self._log.info(f"ServoVirtual '{self.name}' initialized")
        return ImmediateResultTask()

    def close(self) -> None:
        self.enabled = False

    def move_to_angle(self, angle: float) -> Task[()]:
        angle = max(0.0, min(self._angle_range, angle))
        self.current_angle = angle
        self.current_fraction = angle / self._angle_range
        return ImmediateResultTask(None)

    def move_to_fraction(self, fraction: float) -> Task[()]:
        fraction = max(0.0, min(1.0, fraction))
        self.current_fraction = fraction
        self.current_angle = fraction * self._angle_range
        return ImmediateResultTask(None)

    def free(self) -> Task[()]:
        self.enabled = False
        return ImmediateResultTask(None)

    @commands.register(
        args=[],
        result=[("angle", ArgTypes.F32(help="Current commanded angle in degrees"))],
    )
    def get_angle(self) -> Task[float]:
        """Read the last commanded angle."""
        return ImmediateResultTask(self.current_angle)

    @commands.register(
        args=[],
        result=[("fraction", ArgTypes.F32(help="Current position as fraction of full range"))],
    )
    def get_fraction(self) -> Task[float]:
        """Read the last commanded fraction."""
        return ImmediateResultTask(self.current_fraction)

    @commands.register(
        args=[],
        result=[("enabled", ArgTypes.Bool(help="True if the servo is powered (init without subsequent free/close)"))],
    )
    def is_enabled(self) -> Task[bool]:
        """Read whether the simulated servo is enabled."""
        return ImmediateResultTask(self.enabled)


class ServoVirtualDefinition(DriverDefinition):
    """Factory for ServoVirtual from config args."""

    def __init__(self, logger: Logger):
        super().__init__(ServoVirtual.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_optional("angle_range", ArgTypes.F32(), 180.0)
        return defn

    def create(self, args: DriverInitArgs) -> ServoVirtual:
        return ServoVirtual(
            name=args.get_name(),
            logger=self._logger,
            angle_range=args.get("angle_range"),
        )
