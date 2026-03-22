"""Factory for WS2812B LED strip driver."""

from __future__ import annotations

from evo_lib.drivers.ws2812b.config import WS2812BConfig
from evo_lib.interfaces.led_strip import LedStrip


def create_ws2812b(config: WS2812BConfig, *, fake: bool = False) -> LedStrip:
    """Create a WS2812B driver from config.

    Args:
        config: Driver configuration.
        fake: If True, return an in-memory fake for testing.

    Returns:
        A concrete LedStrip implementation (real or fake).
    """
    if fake:
        from evo_lib.drivers.ws2812b.fake import WS2812BFake

        return WS2812BFake(
            name=config.name,
            num_pixels=config.num_pixels,
            brightness=config.brightness,
        )

    from evo_lib.drivers.ws2812b.adafruit import WS2812BAdafruit

    return WS2812BAdafruit(
        name=config.name,
        pin=config.pin,
        num_pixels=config.num_pixels,
        brightness=config.brightness,
    )
