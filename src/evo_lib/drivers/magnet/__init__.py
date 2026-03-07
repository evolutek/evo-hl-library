"""Electromagnet drivers."""

from evo_lib.drivers.magnet.config import MagnetConfig
from evo_lib.drivers.magnet.factory import create_magnet
from evo_lib.drivers.magnet.fake import MagnetFake
from evo_lib.drivers.magnet.gpio_magnet import MagnetGPIO
from evo_lib.interfaces.magnet import Magnet

__all__ = ["Magnet", "MagnetConfig", "MagnetFake", "MagnetGPIO", "create_magnet"]
