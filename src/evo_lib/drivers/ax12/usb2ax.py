"""AX-12A driver: real implementation via libdxl (USB2AX).

Provides AX12Bus (manages the serial connection) and AX12Servo (one per
physical servo, implements the SmartServo interface).
"""

from __future__ import annotations

import ctypes
import logging
import os
from threading import Lock
from time import sleep

from evo_lib.component import Component, ComponentHolder
from evo_lib.interfaces.smart_servo import SmartServo
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)

# AX-12A control table addresses
AX_TORQUE_ENABLE = 24
AX_GOAL_POSITION_L = 30
AX_MOVING_SPEED_L = 32
AX_PRESENT_POSITION_L = 36
AX_PRESENT_SPEED_L = 38
AX_PRESENT_LOAD_L = 40
AX_PRESENT_VOLTAGE = 42
AX_PRESENT_TEMPERATURE = 43

# AX-12A position range: 0-1023 (~300 degrees)
AX_POSITION_MIN = 0
AX_POSITION_MAX = 1023
AX_ANGLE_RANGE = 300.0

# AX-12A speed range: 0-1023 (0 = max speed, 1-1023 = controlled)
AX_SPEED_MAX = 1023

# Search paths for the Dynamixel C library
_LIBDXL_SEARCH = ["/usr/lib", "/usr/local/lib", "."]
_LIBDXL_ENV = os.environ.get("LIBDXL_PATH")
if _LIBDXL_ENV:
    _LIBDXL_SEARCH.insert(0, _LIBDXL_ENV)

# USB2AX device index (first USB serial adapter)
_DEVICE_ID = 0
# Baud rate index for libdxl (1 = 1 Mbps)
_BAUD_RATE_ID = 1


class AX12Bus(ComponentHolder):
    """Manages USB2AX connection, shared by all AX12 servos on the bus."""

    def __init__(self, name: str, device: str, baudrate: int = 1_000_000, retries: int = 3):
        super().__init__(name)
        self.device = device
        self.baudrate = baudrate
        self.retries = retries
        self._dxl = None
        self._lock = Lock()
        self._servos: dict[int, AX12Servo] = {}

    def init(self) -> None:
        for path in _LIBDXL_SEARCH:
            try:
                self._dxl = ctypes.CDLL(os.path.join(path, "libdxl.so"))
                break
            except OSError:
                continue

        if self._dxl is None:
            raise RuntimeError("Cannot load libdxl.so, check LIBDXL_PATH")

        if self._dxl.dxl_initialize(_DEVICE_ID, _BAUD_RATE_ID) != 1:
            raise RuntimeError(f"Cannot initialize AX12 bus on device {self.device}")

        log.info("AX12 bus initialized on %s", self.device)

    def close(self) -> None:
        if self._dxl is not None:
            self._dxl.dxl_terminate()
            self._dxl = None
            log.info("AX12 bus closed")

    def get_subcomponents(self) -> list[Component]:
        return list(self._servos.values())

    def add_servo(self, servo_id: int, name: str) -> AX12Servo:
        """Register and return an AX12Servo for the given ID."""
        if servo_id in self._servos:
            return self._servos[servo_id]
        servo = AX12Servo(name=name, bus=self, servo_id=servo_id)
        self._servos[servo_id] = servo
        return servo

    # Internal methods used by AX12Servo

    def _write_word(self, servo_id: int, address: int, value: int) -> bool:
        """Write a word with retry logic. Returns True on success."""
        for _ in range(self.retries):
            self._dxl.dxl_write_word(servo_id, address, int(value))
            if int(self._dxl.dxl_get_result()) == 1:
                return True
            sleep(0.025)
        log.warning("AX12 ID%d: write failed at addr %d after %d tries", servo_id, address, self.retries)
        return False

    def _read_word(self, servo_id: int, address: int) -> int:
        """Read a word from the control table, with retry logic."""
        for _ in range(self.retries):
            value = int(self._dxl.dxl_read_word(servo_id, address))
            if int(self._dxl.dxl_get_result()) == 1:
                return value
            sleep(0.025)
        log.warning(
            "AX12 ID%d: read failed at addr %d after %d tries", servo_id, address, self.retries
        )
        return value

    def _move(self, servo_id: int, position: int) -> bool:
        with self._lock:
            log.debug("AX12 ID%d -> pos %d", servo_id, position)
            return self._write_word(servo_id, AX_GOAL_POSITION_L, position)

    def _get_position(self, servo_id: int) -> int:
        with self._lock:
            return self._read_word(servo_id, AX_PRESENT_POSITION_L)

    def _set_speed(self, servo_id: int, speed: int) -> bool:
        with self._lock:
            return self._write_word(servo_id, AX_MOVING_SPEED_L, speed)

    def _free(self, servo_id: int) -> bool:
        with self._lock:
            log.debug("AX12 ID%d -> free", servo_id)
            for _ in range(self.retries):
                self._dxl.dxl_write_byte(servo_id, AX_TORQUE_ENABLE, 0)
                if int(self._dxl.dxl_get_result()) == 1:
                    return True
                sleep(0.025)
            return False


class AX12Servo(SmartServo):
    """A single AX-12A servo on a shared bus.

    Position range: 0-1023 over ~300 degrees.
    """

    def __init__(self, name: str, bus: AX12Bus, servo_id: int):
        super().__init__(name)
        self._bus = bus
        self._servo_id = servo_id

    @property
    def servo_id(self) -> int:
        return self._servo_id

    def init(self) -> None:
        # Bus handles initialization
        pass

    def close(self) -> None:
        # Bus handles cleanup
        pass

    # SmartServo interface

    def move_to_position(self, position: int) -> Task[None]:
        if not AX_POSITION_MIN <= position <= AX_POSITION_MAX:
            raise ValueError(
                f"Position {position} out of range [{AX_POSITION_MIN}, {AX_POSITION_MAX}]"
            )
        if not self._bus._move(self._servo_id, position):
            log.warning("AX12 ID%d: move_to_position(%d) failed", self._servo_id, position)
        return ImmediateResultTask(None)

    def get_position(self) -> Task[int]:
        pos = self._bus._get_position(self._servo_id)
        return ImmediateResultTask(pos)

    def get_angle(self) -> Task[float]:
        pos = self._bus._get_position(self._servo_id)
        angle = pos * AX_ANGLE_RANGE / AX_POSITION_MAX
        return ImmediateResultTask(angle)

    def get_fraction(self) -> Task[float]:
        pos = self._bus._get_position(self._servo_id)
        fraction = pos / AX_POSITION_MAX
        return ImmediateResultTask(fraction)

    def set_speed(self, speed: float) -> Task[None]:
        # speed is a fraction 0.0-1.0, convert to native 0-1023
        raw = int(speed * AX_SPEED_MAX)
        raw = max(0, min(AX_SPEED_MAX, raw))
        if not self._bus._set_speed(self._servo_id, raw):
            log.warning("AX12 ID%d: set_speed(%.2f) failed", self._servo_id, speed)
        return ImmediateResultTask(None)

    # Servo interface

    def move_to_angle(self, angle: float) -> Task[None]:
        position = int(angle * AX_POSITION_MAX / AX_ANGLE_RANGE)
        if not AX_POSITION_MIN <= position <= AX_POSITION_MAX:
            raise ValueError(
                f"Angle {angle} maps to position {position}, "
                f"out of range [{AX_POSITION_MIN}, {AX_POSITION_MAX}]"
            )
        if not self._bus._move(self._servo_id, position):
            log.warning("AX12 ID%d: move_to_angle(%.1f) failed", self._servo_id, angle)
        return ImmediateResultTask(None)

    def move_to_fraction(self, fraction: float) -> Task[None]:
        position = int(fraction * AX_POSITION_MAX)
        if not AX_POSITION_MIN <= position <= AX_POSITION_MAX:
            raise ValueError(
                f"Fraction {fraction} maps to position {position}, "
                f"out of range [{AX_POSITION_MIN}, {AX_POSITION_MAX}]"
            )
        if not self._bus._move(self._servo_id, position):
            log.warning("AX12 ID%d: move_to_fraction(%.2f) failed", self._servo_id, fraction)
        return ImmediateResultTask(None)

    def free(self) -> Task[None]:
        if not self._bus._free(self._servo_id):
            log.warning("AX12 ID%d: free() failed", self._servo_id)
        return ImmediateResultTask(None)
