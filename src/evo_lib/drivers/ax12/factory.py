"""Factory functions to create AX12 bus + servos from config."""

from __future__ import annotations

from evo_lib.drivers.ax12.config import AX12BusConfig


def create_ax12_bus(
    config: AX12BusConfig,
    *,
    fake: bool = False,
) -> tuple:
    """Create an AX12 bus and its servos from config.

    Args:
        config: Pydantic config with device path and servo IDs.
        fake: If True, use fake implementations for testing.

    Returns:
        A tuple of (bus, dict[int, servo]) where the dict maps servo IDs
        to servo instances.
    """
    if fake:
        from evo_lib.drivers.ax12.fake import AX12BusFake

        bus = AX12BusFake(
            name=config.name,
            device=config.device,
            baudrate=config.baudrate,
        )
    else:
        from evo_lib.drivers.ax12.usb2ax import AX12Bus

        bus = AX12Bus(
            name=config.name,
            device=config.device,
            baudrate=config.baudrate,
        )

    bus.init()
    servos = {}
    for servo_id in config.servo_ids:
        servos[servo_id] = bus.add_servo(servo_id, f"{config.name}_servo_{servo_id}")

    return bus, servos
