"""Proximity sensor drivers: read-only GPIO wrappers."""

from evo_lib.drivers.proximity.config import ProximityConfig
from evo_lib.drivers.proximity.factory import create_proximity
from evo_lib.drivers.proximity.fake import ProximityFake
from evo_lib.drivers.proximity.gpio_proximity import ProximityGPIO

__all__ = ["ProximityConfig", "ProximityFake", "ProximityGPIO", "create_proximity"]
