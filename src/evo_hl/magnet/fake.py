"""Magnet driver — fake implementation for testing."""

from __future__ import annotations

from evo_hl.magnet.base import Magnet


class MagnetFake(Magnet):
    """In-memory electromagnet for tests and simulation."""

    def __init__(self):
        self.active = False

    def on(self) -> None:
        self.active = True

    def off(self) -> None:
        self.active = False
