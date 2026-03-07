"""Factory for recalibration sensor drivers."""

from __future__ import annotations

from evo_lib.drivers.recal.config import RecalConfig
from evo_lib.interfaces.recal import RecalSensor


def create_recal(config: RecalConfig, *, fake: bool = False) -> RecalSensor:
    """Create a recalibration sensor from configuration.

    When fake=True, returns a RecalFake for testing.
    Otherwise, creates a GPIORpi and wraps it with RecalGPIO.
    """
    if fake:
        from evo_lib.drivers.recal.fake import RecalFake

        return RecalFake(name=config.name)

    from evo_lib.drivers.gpio.rpi import GPIORpi
    from evo_lib.drivers.recal.sensor import RecalGPIO

    gpio = GPIORpi(name=f"{config.name}_gpio", pin=config.gpio_pin)
    return RecalGPIO(name=config.name, gpio=gpio)
