"""Abstract base class for AX-12A Dynamixel servo bus controller."""

from __future__ import annotations

from abc import ABC, abstractmethod
# AX-12A control table addresses
AX_TORQUE_ENABLE = 24
AX_GOAL_POSITION_L = 30
AX_MOVING_SPEED_L = 32
AX_PRESENT_POSITION_L = 36
AX_PRESENT_SPEED_L = 38
AX_PRESENT_LOAD_L = 40
AX_PRESENT_VOLTAGE = 42
AX_PRESENT_TEMPERATURE = 43

# AX-12A position range: 0–1023 (~300°)
AX_POSITION_MIN = 0
AX_POSITION_MAX = 1023

# AX-12A speed range: 0–1023 (0 = max speed, 1–1023 = controlled)
AX_SPEED_MAX = 1023
class AX12(ABC):
    """Controls AX-12A servos on a shared bus (USB2AX or future CAN proxy).

    The bus is shared: one controller instance manages all AX12 on the bus.
    Individual servos are addressed by their Dynamixel ID.
    """

    def __init__(self, device: str, baudrate: int = 1_000_000, retries: int = 3):
        self.device = device
        self.baudrate = baudrate
        self.retries = retries

    @abstractmethod
    def init(self) -> None:
        """Initialize the bus connection."""

    @abstractmethod
    def move(self, servo_id: int, position: int) -> bool:
        """Move servo to position (0–1023). Returns True on success."""

    @abstractmethod
    def set_speed(self, servo_id: int, speed: int) -> bool:
        """Set moving speed (0–1023, 0=max). Returns True on success."""

    @abstractmethod
    def get_position(self, servo_id: int) -> int:
        """Read current position (0–1023)."""

    @abstractmethod
    def free(self, servo_id: int) -> bool:
        """Disable torque on servo (goes limp). Returns True on success."""

    @abstractmethod
    def close(self) -> None:
        """Release bus resources."""
