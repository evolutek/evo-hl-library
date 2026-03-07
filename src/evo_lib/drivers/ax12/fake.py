"""AX-12A driver: fake implementation for testing without hardware.

Provides AX12BusFake and AX12ServoFake with in-memory state tracking.
"""

from __future__ import annotations

import logging

from evo_lib.component import Component, ComponentHolder
from evo_lib.interfaces.smart_servo import SmartServo
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)

# AX-12A position range: 0-1023 (~300 degrees)
AX_POSITION_MIN = 0
AX_POSITION_MAX = 1023
AX_ANGLE_RANGE = 300.0

# AX-12A speed range: 0-1023 (0 = max speed, 1-1023 = controlled)
AX_SPEED_MAX = 1023


class AX12BusFake(ComponentHolder):
    """In-memory AX-12A bus for tests and simulation."""

    def __init__(self, name: str, device: str = "/dev/ttyACM0", baudrate: int = 1_000_000):
        super().__init__(name)
        self.device = device
        self.baudrate = baudrate
        self._servos: dict[int, AX12ServoFake] = {}

    def init(self) -> None:
        log.info("AX12 fake bus initialized on %s", self.device)

    def close(self) -> None:
        for servo in self._servos.values():
            servo._state = {"position": 512, "speed": 0, "torque": True}
        log.info("AX12 fake bus closed")

    def get_subcomponents(self) -> list[Component]:
        return list(self._servos.values())

    def add_servo(self, servo_id: int, name: str) -> AX12ServoFake:
        """Register and return an AX12ServoFake for the given ID."""
        if servo_id in self._servos:
            return self._servos[servo_id]
        servo = AX12ServoFake(name=name, bus=self, servo_id=servo_id)
        self._servos[servo_id] = servo
        return servo


class AX12ServoFake(SmartServo):
    """A single fake AX-12A servo for testing.

    Tracks position, speed, and torque state in memory.
    """

    def __init__(self, name: str, bus: AX12BusFake, servo_id: int):
        super().__init__(name)
        self._bus = bus
        self._servo_id = servo_id
        self._state: dict = {"position": 512, "speed": 0, "torque": True}

    @property
    def servo_id(self) -> int:
        return self._servo_id

    def init(self) -> None:
        pass

    def close(self) -> None:
        pass

    # SmartServo interface

    def move_to_position(self, position: int) -> Task[None]:
        if not AX_POSITION_MIN <= position <= AX_POSITION_MAX:
            raise ValueError(
                f"Position {position} out of range [{AX_POSITION_MIN}, {AX_POSITION_MAX}]"
            )
        self._state["position"] = position
        log.debug("AX12 fake ID%d -> pos %d", self._servo_id, position)
        return ImmediateResultTask(None)

    def get_position(self) -> Task[int]:
        return ImmediateResultTask(self._state["position"])

    def get_angle(self) -> Task[float]:
        angle = self._state["position"] * AX_ANGLE_RANGE / AX_POSITION_MAX
        return ImmediateResultTask(angle)

    def get_fraction(self) -> Task[float]:
        fraction = self._state["position"] / AX_POSITION_MAX
        return ImmediateResultTask(fraction)

    def set_speed(self, speed: float) -> Task[None]:
        raw = int(speed * AX_SPEED_MAX)
        raw = max(0, min(AX_SPEED_MAX, raw))
        self._state["speed"] = raw
        return ImmediateResultTask(None)

    # Servo interface

    def move_to_angle(self, angle: float) -> Task[None]:
        position = int(angle * AX_POSITION_MAX / AX_ANGLE_RANGE)
        if not AX_POSITION_MIN <= position <= AX_POSITION_MAX:
            raise ValueError(
                f"Angle {angle} maps to position {position}, "
                f"out of range [{AX_POSITION_MIN}, {AX_POSITION_MAX}]"
            )
        self._state["position"] = position
        log.debug("AX12 fake ID%d -> angle %.1f (pos %d)", self._servo_id, angle, position)
        return ImmediateResultTask(None)

    def move_to_fraction(self, fraction: float) -> Task[None]:
        position = int(fraction * AX_POSITION_MAX)
        if not AX_POSITION_MIN <= position <= AX_POSITION_MAX:
            raise ValueError(
                f"Fraction {fraction} maps to position {position}, "
                f"out of range [{AX_POSITION_MIN}, {AX_POSITION_MAX}]"
            )
        self._state["position"] = position
        return ImmediateResultTask(None)

    def free(self) -> Task[None]:
        self._state["torque"] = False
        log.debug("AX12 fake ID%d -> free", self._servo_id)
        return ImmediateResultTask(None)
