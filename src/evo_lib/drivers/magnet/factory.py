"""Factory function for Magnet driver instances."""

from __future__ import annotations

from typing import TYPE_CHECKING

from evo_lib.drivers.magnet.config import MagnetConfig

if TYPE_CHECKING:
    from evo_lib.interfaces.gpio import GPIO
    from evo_lib.interfaces.magnet import Magnet


def create_magnet(
    config: MagnetConfig,
    *,
    gpio: GPIO | None = None,
    fake: bool = False,
) -> Magnet:
    """Create a Magnet instance from configuration.

    Args:
        config: Magnet configuration.
        gpio: Pre-built GPIO instance for the magnet pin. Required when fake=False.
        fake: If True, return a MagnetFake (no hardware needed).

    Returns:
        A concrete Magnet implementation.
    """
    if fake:
        from evo_lib.drivers.magnet.fake import MagnetFake

        return MagnetFake(config.name)

    if gpio is None:
        raise ValueError(
            f"Magnet '{config.name}': gpio must be provided when fake=False"
        )

    from evo_lib.drivers.magnet.gpio_magnet import MagnetGPIO

    return MagnetGPIO(config.name, gpio)
