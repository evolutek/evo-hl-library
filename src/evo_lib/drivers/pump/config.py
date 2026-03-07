"""Configuration model for the Pump driver."""

from pydantic import BaseModel, Field


class PumpConfig(BaseModel):
    """Configuration for a GPIO-controlled vacuum pump."""

    name: str
    pump_pin: int = Field(description="GPIO pin for pump motor")
    ev_pin: int | None = Field(
        default=None, description="GPIO pin for electrovalve (optional)"
    )
