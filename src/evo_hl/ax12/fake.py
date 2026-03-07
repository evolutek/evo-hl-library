"""AX-12A driver — fake implementation for testing without hardware."""

from __future__ import annotations

import logging

from evo_hl.ax12.base import AX12, AX_POSITION_MAX, AX_POSITION_MIN

log = logging.getLogger(__name__)


class AX12Fake(AX12):
    """In-memory AX-12A bus for tests and simulation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.servos: dict[int, dict] = {}

    def init(self) -> None:
        self.servos.clear()
        log.info("AX12 fake bus initialized on %s", self.device)

    def _ensure_servo(self, servo_id: int) -> dict:
        """Auto-register a servo on first access."""
        if servo_id not in self.servos:
            self.servos[servo_id] = {
                "position": 512,  # center
                "speed": 0,
                "torque": True,
            }
        return self.servos[servo_id]

    def move(self, servo_id: int, position: int) -> bool:
        if not AX_POSITION_MIN <= position <= AX_POSITION_MAX:
            log.warning("AX12 fake ID%d: position %d out of range", servo_id, position)
            return False
        servo = self._ensure_servo(servo_id)
        servo["position"] = position
        log.debug("AX12 fake ID%d → pos %d", servo_id, position)
        return True

    def set_speed(self, servo_id: int, speed: int) -> bool:
        servo = self._ensure_servo(servo_id)
        servo["speed"] = speed
        return True

    def get_position(self, servo_id: int) -> int:
        return self._ensure_servo(servo_id)["position"]

    def free(self, servo_id: int) -> bool:
        servo = self._ensure_servo(servo_id)
        servo["torque"] = False
        log.debug("AX12 fake ID%d → free", servo_id)
        return True

    def close(self) -> None:
        self.servos.clear()
        log.info("AX12 fake bus closed")
