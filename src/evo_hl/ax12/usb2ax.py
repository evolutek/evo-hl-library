"""AX-12A driver — real implementation via libdxl (USB2AX)."""

from __future__ import annotations

import ctypes
import logging
import os
from threading import Lock
from time import sleep

from evo_hl.ax12.base import (
    AX12,
    AX_GOAL_POSITION_L,
    AX_MOVING_SPEED_L,
    AX_PRESENT_POSITION_L,
    AX_TORQUE_ENABLE,
)

log = logging.getLogger(__name__)

# Search paths for the Dynamixel C library
_LIBDXL_SEARCH = ["/usr/lib", "/usr/local/lib", "."]
_LIBDXL_ENV = os.environ.get("LIBDXL_PATH")
if _LIBDXL_ENV:
    _LIBDXL_SEARCH.insert(0, _LIBDXL_ENV)

# USB2AX device index (first USB serial adapter)
_DEVICE_ID = 0
# Baud rate index for libdxl (1 = 1 Mbps)
_BAUD_RATE_ID = 1


class AX12Usb2ax(AX12):
    """AX-12A bus controller via libdxl and USB2AX."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._dxl = None
        self._lock = Lock()

    def init(self) -> None:
        for path in _LIBDXL_SEARCH:
            try:
                self._dxl = ctypes.CDLL(os.path.join(path, "libdxl.so"))
                break
            except OSError:
                continue

        if self._dxl is None:
            raise RuntimeError("Cannot load libdxl.so — check LIBDXL_PATH")

        if self._dxl.dxl_initialize(_DEVICE_ID, _BAUD_RATE_ID) != 1:
            raise RuntimeError(f"Cannot initialize AX12 bus on device {self.device}")

        log.info("AX12 bus initialized on %s", self.device)

    def _write_word(self, servo_id: int, address: int, value: int) -> bool:
        """Write a word with retry logic. Returns True on success."""
        for attempt in range(self.retries):
            self._dxl.dxl_write_word(servo_id, address, int(value))
            if int(self._dxl.dxl_get_result()) == 1:
                return True
            sleep(0.025)
        log.warning("AX12 ID%d: write failed at addr %d after %d tries", servo_id, address, self.retries)
        return False

    def _read_word(self, servo_id: int, address: int) -> int:
        """Read a word from the control table."""
        return int(self._dxl.dxl_read_word(servo_id, address))

    def move(self, servo_id: int, position: int) -> bool:
        with self._lock:
            log.debug("AX12 ID%d → pos %d", servo_id, position)
            return self._write_word(servo_id, AX_GOAL_POSITION_L, position)

    def set_speed(self, servo_id: int, speed: int) -> bool:
        with self._lock:
            return self._write_word(servo_id, AX_MOVING_SPEED_L, speed)

    def get_position(self, servo_id: int) -> int:
        with self._lock:
            return self._read_word(servo_id, AX_PRESENT_POSITION_L)

    def free(self, servo_id: int) -> bool:
        with self._lock:
            log.debug("AX12 ID%d → free", servo_id)
            for attempt in range(self.retries):
                self._dxl.dxl_write_byte(servo_id, AX_TORQUE_ENABLE, 0)
                if int(self._dxl.dxl_get_result()) == 1:
                    return True
                sleep(0.025)
            return False

    def close(self) -> None:
        if self._dxl is not None:
            self._dxl.dxl_terminate()
            self._dxl = None
            log.info("AX12 bus closed")
