"""I2C motor board driver — Adafruit CircuitPython implementation."""

from __future__ import annotations

import logging
import struct

from evo_hl.motor_board.base import MotorBoard

log = logging.getLogger(__name__)

# Command IDs matching the STM32 firmware protocol
_CMD_HOME = 0x01
_CMD_GOTO = 0x02
_CMD_MOVE = 0x03


class MotorBoardAdafruit(MotorBoard):
    """I2C stepper motor board using Adafruit CircuitPython (any blinka-supported SBC)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._i2c = None

    def init(self) -> None:
        import board
        import busio

        self._i2c = busio.I2C(board.SCL, board.SDA)
        log.info("Motor board initialized at 0x%02x", self.address)

    def _send(self, cmd_id: int, stepper_id: int, data: bytes) -> None:
        self._i2c.writeto(self.address, bytes([cmd_id, stepper_id]) + data)

    def goto(self, stepper_id: int, steps: int, speed: int) -> bool:
        self._send(_CMD_GOTO, stepper_id, struct.pack(">iI", steps, speed))
        log.debug("Motor %d goto %d at speed %d", stepper_id, steps, speed)
        return True

    def move(self, stepper_id: int, steps: int, speed: int) -> bool:
        self._send(_CMD_MOVE, stepper_id, struct.pack(">iI", steps, speed))
        log.debug("Motor %d move %d at speed %d", stepper_id, steps, speed)
        return True

    def home(self, stepper_id: int, speed: int) -> bool:
        self._send(_CMD_HOME, stepper_id, struct.pack(">i", speed))
        log.debug("Motor %d homing at speed %d", stepper_id, speed)
        return True

    def close(self) -> None:
        self._i2c = None
        log.info("Motor board closed")
