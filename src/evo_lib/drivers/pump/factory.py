"""Factory function for Pump driver instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from evo_lib.drivers.pump.config import PumpConfig

if TYPE_CHECKING:
    from evo_lib.interfaces.gpio import GPIO
    from evo_lib.interfaces.pump import Pump


def create_pump(
    config: PumpConfig,
    *,
    gpio_pump: GPIO | None = None,
    gpio_ev: GPIO | None = None,
    fake: bool = False,
) -> Pump:
    """Create a Pump instance from configuration.

    Args:
        config: Pump configuration.
        gpio_pump: Pre-built GPIO instance for the pump pin. Required when fake=False.
        gpio_ev: Pre-built GPIO instance for the electrovalve pin (optional).
        fake: If True, return a PumpFake (no hardware needed).

    Returns:
        A concrete Pump implementation.
    """
    if fake:
        from evo_lib.drivers.pump.fake import PumpFake

        return PumpFake(config.name)

    if gpio_pump is None:
        raise ValueError(
            f"Pump '{config.name}': gpio_pump must be provided when fake=False"
        )

    from evo_lib.drivers.pump.gpio_pump import PumpGPIO

    return PumpGPIO(config.name, pin_pump=gpio_pump, pin_ev=gpio_ev)
