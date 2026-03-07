"""Factory function for ADS1115 driver instantiation from config."""

from __future__ import annotations

from evo_lib.drivers.ads1115.config import ADS1115Config
from evo_lib.drivers.ads1115.adafruit import ADS1115Adafruit
from evo_lib.drivers.ads1115.fake import ADS1115Fake
from evo_lib.interfaces.analog_input import AnalogInput


def create_ads1115(config: ADS1115Config, *, fake: bool = False) -> AnalogInput:
    """Create an ADS1115 analog input from config.

    Returns:
        An ADS1115Adafruit or ADS1115Fake instance.
    """
    if fake:
        return ADS1115Fake(
            name=config.name,
            channel=config.channel,
            address=config.address,
            i2c_bus=config.i2c_bus,
        )
    return ADS1115Adafruit(
        name=config.name,
        channel=config.channel,
        address=config.address,
        i2c_bus=config.i2c_bus,
    )
