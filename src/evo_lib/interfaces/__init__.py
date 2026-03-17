"""Abstract hardware interfaces.

These define the contracts that driver implementations must fulfill.
Robot code depends on these interfaces, never on concrete drivers.
"""

from evo_lib.interfaces.analog_input import AnalogInput
from evo_lib.interfaces.color_sensor import ColorSensor
from evo_lib.interfaces.gpio import GPIO, Edge
from evo_lib.interfaces.led_strip import LedStrip
from evo_lib.interfaces.lidar import Lidar2D
from evo_lib.interfaces.motor_controller import MotorController
from evo_lib.interfaces.servo import Servo
from evo_lib.interfaces.smart_servo import SmartServo

__all__ = [
    "AnalogInput",
    "ColorSensor",
    "Edge",
    "GPIO",
    "LedStrip",
    "Lidar2D",
    "MotorController",
    "Servo",
    "SmartServo",
]
