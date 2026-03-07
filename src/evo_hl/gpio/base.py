"""Abstract base class for GPIO (digital I/O and PWM)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from threading import Thread
from time import sleep

class Edge(Enum):
    """Edge detection mode for input pins."""
    BOTH = 2
    FALLING = 0
    RISING = 1
class GPIO(ABC):
    """Controls digital I/O and PWM on native GPIO pins (e.g., RPi BCM)."""

    @abstractmethod
    def init(self) -> None:
        """Initialize the GPIO subsystem."""

    @abstractmethod
    def setup_input(self, pin: int) -> None:
        """Configure a pin as digital input with pull-down."""

    @abstractmethod
    def setup_output(self, pin: int, default: bool = False) -> None:
        """Configure a pin as digital output."""

    @abstractmethod
    def read(self, pin: int) -> bool:
        """Read digital value from a pin."""

    @abstractmethod
    def write(self, pin: int, value: bool) -> None:
        """Write digital value to an output pin."""

    @abstractmethod
    def setup_pwm(self, pin: int, frequency: float) -> None:
        """Configure a pin for PWM output."""

    @abstractmethod
    def set_pwm(self, pin: int, duty_cycle: float) -> None:
        """Set PWM duty cycle (0.0–100.0) on a configured PWM pin."""

    @abstractmethod
    def stop_pwm(self, pin: int) -> None:
        """Stop PWM on a pin."""

    @abstractmethod
    def close(self) -> None:
        """Release all GPIO resources."""

    def auto_refresh(
        self, pin: int, edge: Edge, interval: float, callback
    ) -> Thread:
        """Poll an input pin and call callback on edge events.

        callback(pin, value) is called when the pin value changes
        according to the edge mode. Returns the polling thread.
        """
        def _poll():
            last = None
            while True:
                sleep(interval)
                value = self.read(pin)
                if last is not None and value != last:
                    if edge == Edge.BOTH or edge.value == value:
                        callback(pin, value)
                last = value

        t = Thread(target=_poll, daemon=True)
        t.start()
        return t
