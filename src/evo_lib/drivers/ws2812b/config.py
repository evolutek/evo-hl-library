"""Configuration model for WS2812B LED strip driver."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WS2812BConfig(BaseModel):
    """Pydantic config for a WS2812B LED strip."""

    name: str
    pin: int = Field(description="GPIO pin for data line")
    num_pixels: int = Field(ge=1)
    brightness: float = Field(default=1.0, ge=0.0, le=1.0)
