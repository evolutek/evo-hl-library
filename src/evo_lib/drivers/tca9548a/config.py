"""Pydantic configuration model for TCA9548A + TCS34725 sensors."""

from pydantic import BaseModel, Field


class TCA9548AConfig(BaseModel):
    """Configuration for a TCA9548A I2C mux with TCS34725 color sensors."""

    name: str
    address: int = Field(default=0x70, description="I2C address of TCA9548A mux")
    i2c_bus: int = Field(default=1)
    channels: dict[int, str] = Field(
        default_factory=dict,
        description="channel number -> sensor name mapping",
    )
