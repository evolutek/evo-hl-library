"""Factory function for RPLidar driver."""

from evo_lib.drivers.rplidar.config import RPLidarConfig
from evo_lib.interfaces.lidar import Lidar2D


def create_rplidar(config: RPLidarConfig, *, fake: bool = False) -> Lidar2D:
    """Create an RPLidar instance from config.

    When fake=True, returns a fake implementation for testing.
    """
    if fake:
        from evo_lib.drivers.rplidar.fake import RPLidarFake

        return RPLidarFake(name=config.name)

    from evo_lib.drivers.rplidar.serial import RPLidarSerial

    return RPLidarSerial(
        name=config.name,
        device=config.device,
        baudrate=config.baudrate,
    )
