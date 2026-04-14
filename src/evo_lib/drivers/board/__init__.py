"""Custom Evolutek boards: aggregators of standalone chips with no MCU.

A board driver in this package is a pure composition helper over chip-level
drivers (MCP23017, PCA9685, TCA9548A, ...). It owns the child peripherals,
chains their lifecycle, and exposes them through get_subcomponents().

Boards with a MCU running custom firmware (e.g. Carte Stepper, Carte
Localisation) do NOT belong here: they speak a bespoke protocol and live
under their transport (CAN, serial, ...) rather than in this aggregation
layer.
"""

from evo_lib.drivers.board.base import BoardDriver

__all__ = ["BoardDriver"]
