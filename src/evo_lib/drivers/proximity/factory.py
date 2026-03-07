"""Factory for proximity sensor drivers."""

from __future__ import annotations

from evo_lib.drivers.proximity.config import ProximityConfig
from evo_lib.interfaces.proximity import ProximitySensor


def create_proximity(config: ProximityConfig, *, fake: bool = False) -> ProximitySensor:
    """Create a proximity sensor from configuration.

    When fake=True, returns a ProximityFake for testing.
    Otherwise, creates a GPIORpi and wraps it with ProximityGPIO.
    """
    if fake:
        from evo_lib.drivers.proximity.fake import ProximityFake

        return ProximityFake(name=config.name, pin=config.pin)

    from evo_lib.drivers.gpio.rpi import GPIORpi
    from evo_lib.drivers.proximity.gpio_proximity import ProximityGPIO

    gpio = GPIORpi(name=f"{config.name}_gpio", pin=config.pin)
    return ProximityGPIO(name=config.name, gpio=gpio)
