"""Pilot drivers: virtual implementations for testing and simulation.

Simulates movement with linear interpolation in a background thread,
similar to the legacy fake_trajman.py.
"""

import logging
import math
import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.interfaces.pilot import (
    DifferentialPilot,
    DifferentialPilotWaypoint,
    HolonomicPilot,
    HolonomicPilotWaypoint,
    PilotMoveStatus,
)
from evo_lib.logger import Logger
from evo_lib.task import DelayedTask, ImmediateResultTask, Task


class PilotVirtual(DifferentialPilot):
    """Simulated pilot for testing and development without hardware."""

    def __init__(
        self,
        name: str,
        speed_trsl: float = 200.0,
        speed_rot: float = 2.0,
        logger: logging.Logger | None = None,
    ):
        super().__init__(name)
        self._speed_trsl = speed_trsl  # mm/s
        self._speed_rot = speed_rot  # rad/s
        self._log = logger or logging.getLogger(__name__)
        self._x: float = 0.0
        self._y: float = 0.0
        self._theta: float = 0.0
        self._lock = threading.Lock()
        self._current_task: DelayedTask[PilotMoveStatus] | None = None
        self._cancel = threading.Event()

    @property
    def position(self) -> tuple[float, float, float]:
        with self._lock:
            return (self._x, self._y, self._theta)

    def init(self) -> None:
        self._log.info("PilotVirtual '%s' initialized", self.name)

    def close(self) -> None:
        self._cancel.set()

    def go_to(self, x: float, y: float) -> Task[PilotMoveStatus]:
        dx = x - self._x
        dy = y - self._y
        distance = math.sqrt(dx * dx + dy * dy)
        if distance < 0.1:
            return ImmediateResultTask(PilotMoveStatus.REACHED)
        heading = math.atan2(dy, dx)
        duration = distance / self._speed_trsl
        return self._start_move(x, y, heading, duration)

    def go_to_then_head_to(self, x: float, y: float, heading: float) -> Task[PilotMoveStatus]:
        # TODO: chain go_to + rotation to heading after arrival
        return self.go_to(x, y)

    def go_to_then_rotate(self, x: float, y: float, angle: float) -> Task[PilotMoveStatus]:
        # TODO: chain go_to + relative rotation after arrival
        return self.go_to(x, y)

    def go_to_then_look_at(
        self, x: float, y: float, look_x: float, look_y: float
    ) -> Task[PilotMoveStatus]:
        # TODO: chain go_to + look_at after arrival
        return self.go_to(x, y)

    def forward(self, distance: float) -> Task[PilotMoveStatus]:
        target_x = self._x + distance * math.cos(self._theta)
        target_y = self._y + distance * math.sin(self._theta)
        duration = abs(distance) / self._speed_trsl
        return self._start_move(target_x, target_y, self._theta, duration)

    def head_to(self, heading: float) -> Task[PilotMoveStatus]:
        duration = abs(heading - self._theta) / self._speed_rot
        return self._start_rotation(heading, duration)

    def look_at(self, x: float, y: float) -> Task[PilotMoveStatus]:
        heading = math.atan2(y - self._y, x - self._x)
        return self.head_to(heading)

    def rotate(self, angle: float) -> Task[PilotMoveStatus]:
        target = self._theta + angle
        duration = abs(angle) / self._speed_rot
        return self._start_rotation(target, duration)

    def follow_path(self, waypoints: list[DifferentialPilotWaypoint]) -> Task[PilotMoveStatus]:
        # TODO: simulate sequential traversal of all waypoints
        if not waypoints:
            return ImmediateResultTask(PilotMoveStatus.REACHED)
        wp = waypoints[-1]
        return self.go_to(wp.x, wp.y)

    def stop(self) -> Task[None]:
        self._cancel.set()
        if self._current_task is not None:
            self._current_task.complete(PilotMoveStatus.CANCELLED)
            self._current_task = None
        return ImmediateResultTask(None)

    def free(self) -> Task[None]:
        self._cancel.set()
        return ImmediateResultTask(None)

    # --- Internal ---

    def _start_move(
        self, x: float, y: float, heading: float, duration: float
    ) -> Task[PilotMoveStatus]:
        task = DelayedTask[PilotMoveStatus]()
        self._current_task = task
        self._cancel.clear()
        t = threading.Thread(
            target=self._simulate_move,
            args=(x, y, heading, duration, task),
            daemon=True,
        )
        t.start()
        return task

    def _start_rotation(self, heading: float, duration: float) -> Task[PilotMoveStatus]:
        task = DelayedTask[PilotMoveStatus]()
        self._current_task = task
        self._cancel.clear()
        t = threading.Thread(
            target=self._simulate_rotation,
            args=(heading, duration, task),
            daemon=True,
        )
        t.start()
        return task

    def _simulate_move(
        self,
        target_x: float,
        target_y: float,
        heading: float,
        duration: float,
        task: DelayedTask[PilotMoveStatus],
    ) -> None:
        if self._cancel.wait(timeout=duration):
            return  # Cancelled
        with self._lock:
            self._x = target_x
            self._y = target_y
            self._theta = heading
        task.complete(PilotMoveStatus.REACHED)

    def _simulate_rotation(
        self,
        heading: float,
        duration: float,
        task: DelayedTask[PilotMoveStatus],
    ) -> None:
        if self._cancel.wait(timeout=duration):
            return  # Cancelled
        with self._lock:
            self._theta = heading
        task.complete(PilotMoveStatus.REACHED)


class PilotVirtualDefinition(DriverDefinition):
    """Factory for PilotVirtual from config args."""

    def __init__(self, logger: Logger):
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        defn.add_optional("speed_trsl", ArgTypes.F32(), 200.0)
        defn.add_optional("speed_rot", ArgTypes.F32(), 2.0)
        return defn

    def create(self, args: DriverInitArgs) -> PilotVirtual:
        name = args.get("name")
        return PilotVirtual(
            name=name,
            speed_trsl=args.get("speed_trsl"),
            speed_rot=args.get("speed_rot"),
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )


class HolonomicPilotVirtual(PilotVirtual, HolonomicPilot):
    """Simulated holonomic pilot: simultaneous translation+rotation."""

    def go_to_while_head_to(self, x: float, y: float, heading: float) -> Task[PilotMoveStatus]:
        dx = x - self._x
        dy = y - self._y
        distance = math.sqrt(dx * dx + dy * dy)
        duration = max(distance / self._speed_trsl, abs(heading - self._theta) / self._speed_rot)
        if duration < 0.001:
            return ImmediateResultTask(PilotMoveStatus.REACHED)
        return self._start_move(x, y, heading, duration)

    def go_to_while_rotate(self, x: float, y: float, angle: float) -> Task[PilotMoveStatus]:
        target_theta = self._theta + angle
        return self.go_to_while_head_to(x, y, target_theta)

    def go_to_while_look_at(
        self, x: float, y: float, look_x: float, look_y: float
    ) -> Task[PilotMoveStatus]:
        heading = math.atan2(look_y - y, look_x - x)
        return self.go_to_while_head_to(x, y, heading)

    def follow_holonomic_path(
        self, waypoints: list[HolonomicPilotWaypoint]
    ) -> Task[PilotMoveStatus]:
        # TODO: simulate sequential traversal of all waypoints
        if not waypoints:
            return ImmediateResultTask(PilotMoveStatus.REACHED)
        wp = waypoints[-1]
        return self.go_to_while_head_to(wp.x, wp.y, wp.heading)


class HolonomicPilotVirtualDefinition(DriverDefinition):
    """Factory for HolonomicPilotVirtual from config args."""

    def __init__(self, logger: Logger):
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        defn.add_optional("speed_trsl", ArgTypes.F32(), 200.0)
        defn.add_optional("speed_rot", ArgTypes.F32(), 2.0)
        return defn

    def create(self, args: DriverInitArgs) -> HolonomicPilotVirtual:
        name = args.get("name")
        return HolonomicPilotVirtual(
            name=name,
            speed_trsl=args.get("speed_trsl"),
            speed_rot=args.get("speed_rot"),
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
