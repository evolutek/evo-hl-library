"""Configuration model for the Magnet driver."""

from pydantic import BaseModel, Field


class MagnetConfig(BaseModel):
    """Configuration for a GPIO-controlled electromagnet."""

    name: str
    gpio_pin: int = Field(description="GPIO pin controlling the electromagnet")
