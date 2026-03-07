"""Configuration model for recalibration sensors."""

from pydantic import BaseModel, Field


class RecalConfig(BaseModel):
    name: str
    gpio_pin: int = Field(description="GPIO pin number")
    active_low: bool = Field(default=True, description="True if sensor is active-low")
