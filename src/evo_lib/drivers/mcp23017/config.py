"""Pydantic configuration model for MCP23017 GPIO expander."""

from pydantic import BaseModel, Field


class MCP23017Config(BaseModel):
    """Configuration for a single MCP23017 chip and its pins."""

    name: str
    address: int = Field(default=0x20, description="I2C address")
    i2c_bus: int = Field(default=1, description="I2C bus number")
    pins: dict[int, str] = Field(
        default_factory=dict,
        description="Mapping of pin number (0-15) to pin name",
    )
