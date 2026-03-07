"""Pydantic configuration model for AX12 bus and servos."""

from pydantic import BaseModel, Field


class AX12BusConfig(BaseModel):
    """Configuration for an AX12 bus (USB2AX) with its servos."""

    name: str
    device: str = Field(default="/dev/ttyACM0", description="Serial device path")
    baudrate: int = Field(default=1_000_000)
    servo_ids: list[int] = Field(
        default_factory=list,
        description="AX12 servo IDs to register on this bus",
    )
