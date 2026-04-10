"""Base classes for all hardware peripherals."""

from abc import ABC, abstractmethod

from evo_lib.driver_definition import DriverDefinition, DriverInitArgs
from evo_lib.task import Task


class Peripheral(ABC):
    """
    Lifecycle contract shared by every hardware peripheral.

    Every driver (real or virtual) inherits from this and implements
    ``init`` (acquire resources) and ``close`` (release them).
    """

    def __init__(self, name: str):
        self._name = name
        # Set by the ComponentsManager right after DriverDefinition.create()
        # returns. Sub-components not instantiated through the ComponentsManager
        # (e.g. MCP23017Pin built via get_pin) may leave this as None; calling
        # get_definition() on them will then raise.
        self._definition: DriverDefinition | None = None
        self._init_args: DriverInitArgs | None = None
        self._dependencies: set[Peripheral] = set()
        self._dependents: set[Peripheral] = set()
        self._required: bool = True # TODO: Use a value from config

    def add_dependency(self, peripheral: Peripheral) -> None:
        self._dependencies.add(peripheral)

    def add_dependent(self, peripheral: Peripheral) -> None:
        self._dependents.add(peripheral)

    def get_dependencies(self) -> set[Peripheral]:
        return self._dependencies

    def get_dependents(self) -> set[Peripheral]:
        return self._dependents

    def is_required(self) -> bool:
        return self._required

    @property
    def name(self) -> str:
        """Return the name of this peripheral instance."""
        return self._name

    def get_init_args(self) -> DriverInitArgs:
        if self._init_args is None:
            raise RuntimeError(
                f"Peripheral '{self._name}' has no init arguments "
                "(not instantiated through the ComponentsManager?)"
            )
        return self._init_args

    def get_definition(self) -> DriverDefinition:
        """Return the DriverDefinition this peripheral was instantiated from."""
        if self._definition is None:
            raise RuntimeError(
                f"Peripheral '{self._name}' has no linked DriverDefinition "
                "(not instantiated through the ComponentsManager?)"
            )
        return self._definition

    @abstractmethod
    def init(self) -> Task[()]:
        """Acquire hardware resources."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""


class Interface(Peripheral):
    """A hardware interface (bus or I/O protocol).

    Subclasses define protocol-specific methods (I2C, Serial, GPIO, etc.).
    """


class InterfaceHolder(Peripheral):
    """A peripheral that manages child peripherals.

    For example, an MCP23017 chip exposes 16 GPIO pins.
    """

    @abstractmethod
    def get_subcomponents(self) -> list[Peripheral]:
        """Return the list of child peripherals managed by this holder."""


class Placable(Peripheral):
    """A peripheral with a physical position on the robot."""
