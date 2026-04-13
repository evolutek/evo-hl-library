"""Serial drivers: real and virtual implementations."""

from evo_lib.drivers.serial.rpi import (
    RpiSerial,
    RpiSerialDefinition,
    RpiSerialVirtual,
    RpiSerialVirtualDefinition,
)
from evo_lib.drivers.serial.virtual import SerialVirtual, SerialVirtualDefinition

__all__ = [
    "RpiSerial",
    "RpiSerialDefinition",
    "RpiSerialVirtual",
    "RpiSerialVirtualDefinition",
    "SerialVirtual",
    "SerialVirtualDefinition",
]
