"""Configuration model for proximity sensors."""

from pydantic import BaseModel, Field


class ProximityConfig(BaseModel):
    name: str
    pin: int = Field(description="GPIO pin number")
