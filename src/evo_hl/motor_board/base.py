"""Abstract base class for I2C stepper motor controller board."""

from __future__ import annotations

from abc import ABC, abstractmethod

class MotorBoard(ABC):
    """Controls stepper motors via a custom I2C motor board."""

    def __init__(self, address: int = 0x69):
        self.address = address

    @abstractmethod
    def init(self) -> None:
        """Initialize I2C communication."""

    @abstractmethod
    def goto(self, stepper_id: int, steps: int, speed: int) -> bool:
        """Move stepper to absolute position (steps) at given speed."""

    @abstractmethod
    def move(self, stepper_id: int, steps: int, speed: int) -> bool:
        """Move stepper by relative steps at given speed."""

    @abstractmethod
    def home(self, stepper_id: int, speed: int) -> bool:
        """Home the stepper at given speed."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""
