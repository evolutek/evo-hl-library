"""Pydantic config model for SICK TIM driver."""

from pydantic import BaseModel, Field


class SickTIMConfig(BaseModel):
    name: str
    host: str = Field(default="192.168.0.1")
    port: int = Field(default=2112)
