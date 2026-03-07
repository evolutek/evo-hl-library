"""Factory function for SICK TIM driver."""

from evo_lib.drivers.tim.config import SickTIMConfig
from evo_lib.interfaces.lidar import Lidar2D


def create_sick_tim(config: SickTIMConfig, *, fake: bool = False) -> Lidar2D:
    """Create a SICK TIM instance from config.

    When fake=True, returns a fake implementation for testing.
    """
    if fake:
        from evo_lib.drivers.tim.fake import SickTIMFake

        return SickTIMFake(name=config.name, host=config.host, port=config.port)

    from evo_lib.drivers.tim.sensor import SickTIM

    return SickTIM(name=config.name, host=config.host, port=config.port)
