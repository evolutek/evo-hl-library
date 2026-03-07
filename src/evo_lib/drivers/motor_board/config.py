"""Configuration model for Motor Board driver."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MotorBoardConfig(BaseModel):
    """Pydantic config for a Motor Board."""

    name: str
    address: int = Field(default=0x69, description="I2C address")
    i2c_bus: int = Field(default=1)
