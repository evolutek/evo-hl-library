"""Pydantic config model for RPLidar driver."""

from pydantic import BaseModel, Field


class RPLidarConfig(BaseModel):
    name: str
    device: str = Field(default="/dev/ttyUSB0")
    baudrate: int = Field(default=115200)
