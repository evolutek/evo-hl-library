"""ADS1115 16-bit ADC drivers (one channel per instance)."""

from evo_lib.drivers.ads1115.adafruit import ADS1115Adafruit
from evo_lib.drivers.ads1115.config import ADS1115Config
from evo_lib.drivers.ads1115.factory import create_ads1115
from evo_lib.drivers.ads1115.fake import ADS1115Fake

__all__ = ["ADS1115Adafruit", "ADS1115Fake", "ADS1115Config", "create_ads1115"]
