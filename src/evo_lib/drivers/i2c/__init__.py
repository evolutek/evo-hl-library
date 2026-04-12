"""I2C drivers: real and virtual implementations."""

from evo_lib.drivers.i2c.rpi import RpiI2C, RpiI2CDefinition, RpiI2CVirtual, RpiI2CVirtualDefinition
from evo_lib.drivers.i2c.tca9548a import (
    TCA9548A,
    TCA9548ADefinition,
    TCA9548AVirtual,
    TCA9548AVirtualDefinition,
)
from evo_lib.drivers.i2c.virtual import I2CVirtual

__all__ = [
    "I2CVirtual",
    "RpiI2C",
    "RpiI2CDefinition",
    "RpiI2CVirtual",
    "RpiI2CVirtualDefinition",
    "TCA9548A",
    "TCA9548ADefinition",
    "TCA9548AVirtual",
    "TCA9548AVirtualDefinition",
]
