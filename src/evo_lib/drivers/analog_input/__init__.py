"""AnalogInput drivers: real and virtual implementations."""

from evo_lib.drivers.analog_input.ads1115 import (
    ADS1115Channel,
    ADS1115ChannelDefinition,
    ADS1115Chip,
    ADS1115ChipDefinition,
)
from evo_lib.drivers.analog_input.virtual import (
    ADS1115ChannelVirtualDefinition,
    ADS1115ChipVirtual,
    ADS1115ChipVirtualDefinition,
    AnalogInputChipVirtual,
    AnalogInputVirtual,
)

__all__ = [
    "ADS1115Channel",
    "ADS1115ChannelDefinition",
    "ADS1115ChannelVirtualDefinition",
    "ADS1115Chip",
    "ADS1115ChipDefinition",
    "ADS1115ChipVirtual",
    "ADS1115ChipVirtualDefinition",
    "AnalogInputChipVirtual",
    "AnalogInputVirtual",
]
