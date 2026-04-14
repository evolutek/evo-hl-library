"""Lightweight standalone SmartServo simulator (no bus, no protocol).

Useful for higher-level tests that want to assert on movement orders
without caring about Dynamixel framing. For a full AX-12 virtual stack,
use AX12BusVirtual + AX12 from ax12.py instead.
"""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.smart_servo import SmartServo
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task

_POSITION_MAX = 1023
_ANGLE_MAX = 300.0


class SmartServoVirtual(SmartServo):
    """In-memory smart servo for tests and simulation."""

    def __init__(self, name: str, logger: Logger, servo_id: int = 1):
        super().__init__(name)
        self._log = logger
        self._id = servo_id
        self._position: int = 0
        self._speed: float = 1.0
        self._torque_enabled: bool = False

    def init(self) -> Task[()]:
        self._torque_enabled = True
        self._log.info(f"SmartServoVirtual '{self.name}' (ID {self._id}) initialized")
        return ImmediateResultTask()

    def close(self) -> None:
        self._torque_enabled = False

    def move_to_angle(self, angle: float) -> Task[()]:
        angle = max(0.0, min(_ANGLE_MAX, angle))
        return self.move_to_position(round(angle / _ANGLE_MAX * _POSITION_MAX))

    def move_to_fraction(self, fraction: float) -> Task[()]:
        fraction = max(0.0, min(1.0, fraction))
        return self.move_to_position(round(fraction * _POSITION_MAX))

    def move_to_position(self, position: int) -> Task[()]:
        self._position = max(0, min(_POSITION_MAX, position))
        return ImmediateResultTask()

    def get_position(self) -> Task[int]:
        return ImmediateResultTask(self._position)

    def get_angle(self) -> Task[float]:
        return ImmediateResultTask(self._position / _POSITION_MAX * _ANGLE_MAX)

    def get_fraction(self) -> Task[float]:
        return ImmediateResultTask(self._position / _POSITION_MAX)

    def set_speed(self, speed: float) -> Task[()]:
        self._speed = max(0.0, min(1.0, speed))
        return ImmediateResultTask()

    def free(self) -> Task[()]:
        self._torque_enabled = False
        return ImmediateResultTask()

    def inject_position(self, position: int) -> None:
        """Set position value for testing."""
        self._position = position


class SmartServoVirtualDefinition(DriverDefinition):
    """Factory for SmartServoVirtual from config args."""

    def __init__(self, logger: Logger):
        super().__init__()
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_optional("id", ArgTypes.U8(), 1)
        return defn

    def create(self, args: DriverInitArgs) -> SmartServoVirtual:
        return SmartServoVirtual(
            name=args.get_name(),
            logger=self._logger,
            servo_id=args.get("id"),
        )
