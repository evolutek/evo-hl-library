"""Base class for all hardware components."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Component(ABC):
    """
    Lifecycle contract shared by every hardware component.

    Every driver (real or fake) inherits from this and implements
    ``init`` (acquire resources) and ``close`` (release them).
    """

    def __init__(self, name: str):
        self._name = name

    def get_name(self) -> str:
        """Return the name of this component instance."""
        return self._name

    @abstractmethod
    def init(self) -> None:
        """Acquire hardware resources."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""


class ComponentHolder(Component):
    """
    Like Component but have a method ``get_subcomponents`` that return the
    list of components managed by this one.
    """

    def __init__(self, name: str):
        super().__init__(name)

    @abstractmethod
    def get_subcomponents(self) -> list[Component]:
        """Return this list of child components managed by this component holder."""
