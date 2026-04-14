"""BoardDriver: base class for passthrough Evolutek boards.

A passthrough board has no microcontroller of its own. The parent bus
(I2C, SPI, GPIO, ...) traverses the board to reach the underlying chips,
so the driver never issues a "board-level" command: it just owns the
children and chains their lifecycle.

Subclasses instantiate the concrete children in their own __init__ and
hand the list to super().__init__(). The base class stays agnostic about
the number and kind of parent buses: a board mixing I2C + SPI + native
GPIO is fine, each child carries its own dependencies.
"""

from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.task import ImmediateResultTask, Task


class BoardDriver(InterfaceHolder):
    """Composition helper for passthrough boards.

    Owns a fixed list of child peripherals, chains init() in declaration
    order and close() in reverse. Exposes children through get_subcomponents()
    so the rest of the library (registry, introspection, virtual swaps) sees
    the full peripheral tree.
    """

    def __init__(self, name: str, logger: Logger, children: list[Peripheral]):
        super().__init__(name)
        self._log = logger
        self._children = children

    def init(self) -> Task[()]:
        for child in self._children:
            child.init().wait()
        self._log.info(f"Board '{self.name}' initialized ({len(self._children)} sub-components)")
        return ImmediateResultTask()

    def close(self) -> None:
        # Reverse order so dependents close before their dependencies.
        for child in reversed(self._children):
            try:
                child.close()
            except Exception as exc:
                self._log.warning(f"Board '{self.name}': error closing '{child.name}': {exc}")
        self._log.info(f"Board '{self.name}' closed")

    def get_subcomponents(self) -> list[Peripheral]:
        return list(self._children)
