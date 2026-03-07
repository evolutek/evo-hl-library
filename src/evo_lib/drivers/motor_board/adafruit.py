"""I2C motor board driver, Adafruit CircuitPython implementation."""

from __future__ import annotations

import logging
import struct

from evo_lib.drivers.motor_board.base import MotorBoard
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)

# Command IDs matching the STM32 firmware protocol
_CMD_HOME = 0x01
_CMD_GOTO = 0x02
_CMD_MOVE = 0x03


class MotorBoardAdafruit(MotorBoard):
    """I2C stepper motor board using Adafruit CircuitPython (any blinka-supported SBC)."""

    def __init__(self, name: str = "motor_board", **kwargs):
        super().__init__(name, **kwargs)
        self._i2c = None

    def init(self) -> None:
        import board
        import busio

        self._i2c = busio.I2C(board.SCL, board.SDA)
        log.info("Motor board initialized at 0x%02x", self.address)

    def _require_init(self) -> None:
        """Raise if the I2C bus has not been initialized."""
        if self._i2c is None:
            raise RuntimeError("Motor board not initialized")

    def _send(self, cmd_id: int, stepper_id: int, data: bytes) -> Task[bool]:
        """Send a command over I2C. Returns an immediate task with success status."""
        self._require_init()
        try:
            self._i2c.writeto(self.address, bytes([cmd_id, stepper_id]) + data)
        except OSError as exc:
            log.error("I2C write failed for motor board at 0x%02x: %s", self.address, exc)
            return ImmediateResultTask(False)
        return ImmediateResultTask(True)

    def goto(self, stepper_id: int, steps: int, speed: int) -> Task[bool]:
        result = self._send(_CMD_GOTO, stepper_id, struct.pack(">iI", steps, speed))
        log.debug("Motor %d goto %d at speed %d", stepper_id, steps, speed)
        return result

    def move(self, stepper_id: int, steps: int, speed: int) -> Task[bool]:
        result = self._send(_CMD_MOVE, stepper_id, struct.pack(">iI", steps, speed))
        log.debug("Motor %d move %d at speed %d", stepper_id, steps, speed)
        return result

    def home(self, stepper_id: int, speed: int) -> Task[bool]:
        result = self._send(_CMD_HOME, stepper_id, struct.pack(">i", speed))
        log.debug("Motor %d homing at speed %d", stepper_id, speed)
        return result

    def close(self) -> None:
        if self._i2c is not None:
            self._i2c.deinit()
            self._i2c = None
        log.info("Motor board closed")
