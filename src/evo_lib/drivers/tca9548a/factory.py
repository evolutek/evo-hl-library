"""Factory functions to create TCA9548A + sensors from config."""

from __future__ import annotations

from evo_lib.drivers.tca9548a.config import TCA9548AConfig


def create_tca9548a(
    config: TCA9548AConfig,
    *,
    fake: bool = False,
) -> tuple:
    """Create a TCA9548A mux and its TCS34725 sensors from config.

    Args:
        config: Pydantic config with mux address and channel->name mapping.
        fake: If True, use fake implementations for testing.

    Returns:
        A tuple of (mux, dict[int, sensor]) where the dict maps channel
        numbers to sensor instances.
    """
    if fake:
        from evo_lib.drivers.tca9548a.fake import TCA9548AFake

        mux = TCA9548AFake(
            name=config.name,
            i2c_bus=config.i2c_bus,
            address=config.address,
        )
    else:
        from evo_lib.drivers.tca9548a.adafruit import TCA9548A

        mux = TCA9548A(
            name=config.name,
            i2c_bus=config.i2c_bus,
            address=config.address,
        )

    sensors = {}
    mux.init()
    for channel, sensor_name in config.channels.items():
        sensors[channel] = mux.get_sensor(channel, sensor_name)

    return mux, sensors
