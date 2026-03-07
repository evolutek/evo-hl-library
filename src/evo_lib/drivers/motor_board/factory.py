"""Factory for Motor Board driver."""

from __future__ import annotations

from evo_lib.drivers.motor_board.base import MotorBoard
from evo_lib.drivers.motor_board.config import MotorBoardConfig


def create_motor_board(config: MotorBoardConfig, *, fake: bool = False) -> MotorBoard:
    """Create a Motor Board driver from config.

    Args:
        config: Driver configuration.
        fake: If True, return an in-memory fake for testing.

    Returns:
        A concrete MotorBoard implementation (real or fake).
    """
    if fake:
        from evo_lib.drivers.motor_board.fake import MotorBoardFake

        return MotorBoardFake(name=config.name, address=config.address)

    from evo_lib.drivers.motor_board.adafruit import MotorBoardAdafruit

    return MotorBoardAdafruit(name=config.name, address=config.address)
