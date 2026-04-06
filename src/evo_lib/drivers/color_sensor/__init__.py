"""ColorSensor drivers: real and virtual implementations."""

from evo_lib.drivers.color_sensor.tcs34725 import TCS34725, TCS34725Definition
from evo_lib.drivers.color_sensor.virtual import ColorSensorVirtual, ColorSensorVirtualDefinition

__all__ = [
    "ColorSensorVirtual",
    "ColorSensorVirtualDefinition",
    "TCS34725",
    "TCS34725Definition",
]
