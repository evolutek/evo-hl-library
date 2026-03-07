"""Pydantic configuration model for ADS1115 ADC."""

from pydantic import BaseModel, Field


class ADS1115Config(BaseModel):
    """Configuration for a single ADS1115 analog input channel."""

    name: str
    channel: int = Field(ge=0, le=3, description="ADC channel (0-3)")
    address: int = Field(default=0x48, description="I2C address")
    i2c_bus: int = Field(default=1, description="I2C bus number")
