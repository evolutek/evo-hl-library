"""Magnet driver: fake implementation for testing."""

from __future__ import annotations

import logging

from evo_lib.interfaces.magnet import Magnet
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)


class MagnetFake(Magnet):
    """In-memory electromagnet for tests and simulation."""

    def __init__(self, name: str):
        super().__init__(name)
        self._active: bool = False

    def init(self) -> None:
        self._active = False
        log.info("MagnetFake '%s' initialized", self._name)

    def close(self) -> None:
        self._active = False
        log.info("MagnetFake '%s' closed", self._name)

    def activate(self) -> Task[None]:
        self._active = True
        return ImmediateResultTask(None)

    def deactivate(self) -> Task[None]:
        self._active = False
        return ImmediateResultTask(None)

    def is_active(self) -> Task[bool]:
        return ImmediateResultTask(self._active)
