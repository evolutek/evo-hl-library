"""Proximity sensor — implementation via GPIO pins."""

from __future__ import annotations

import logging

from evo_hl.gpio.base import GPIO
from evo_hl.proximity.base import Proximity

log = logging.getLogger(__name__)


class ProximityGPIO(Proximity):
    """Proximity sensors reading digital GPIO inputs."""

    def __init__(self, gpio: GPIO, pin_map: dict[int, int]):
        """
        Args:
            gpio: GPIO driver instance.
            pin_map: sensor_id → GPIO pin number mapping.
        """
        self._gpio = gpio
        self._pin_map = pin_map

    def read(self, sensor_id: int) -> bool:
        pin = self._pin_map.get(sensor_id)
        if pin is None:
            raise ValueError(f"Unknown sensor ID {sensor_id}")
        return self._gpio.read(pin)
