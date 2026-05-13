"""Avoidance handler Actor for the Trajman brique.

Runs in its own thread, continuously monitoring detected obstacles
(from lidar or other sensors). Can preemptively stop the Pilot when
an obstacle is detected during movement.

Also exposes telemetry data via an Event for the simulator and WorldModel.
"""

from dataclasses import dataclass
from threading import Event as ThreadEvent
from threading import Lock, Thread

from evo_lib.event import Event
from evo_lib.interfaces.obstacles_provider import Obstacle
from evo_lib.logger import Logger
from evo_lib.types.pose import Pose2D
from evo_lib.types.vect import Vect2D

# Table dimensions (mm)
TABLE_X: float = 3000.0
TABLE_Y: float = 2000.0


@dataclass
class AvoidanceParameters:
    deceleration: float = (
        500  # The robot deceleration in mm/s^2 (influences the detection range)
    )
    latency: float = (
        0.5  # The detection latency in second (influences the detection range)
    )
    rectangle_length: float = 300  # How far to avoid in front of the moving direction (half width of the robot plus the opponent robot)
    rectangle_width: float = 600  # How far to avoid on the side of the moving direction of the robot (width of the robot plus the opponent robot)


class AvoidanceHandler:
    def __init__(self, logger: Logger, parameters: AvoidanceParameters):
        self._logger = logger
        self._parameters = parameters
        self._running: bool = False
        self._update_event = ThreadEvent()
        self._enabled: bool = False
        self._lock = Lock()
        self._thread: Thread | None = None
        self._avoid_event: Event[bool] = Event()
        self._obstacles: list[Obstacle] = []
        self._pose: Pose2D = Pose2D()
        # Arbitrary non-null velocity to keep track of
        # the last direction of movement when the robot is stopped
        self._last_non_null_velocity: Vect2D = Vect2D(
            1, 0
        )  # TODO: Maybe use the heading of the robot instead of an arbitrary velocity
        self._velocity: Vect2D = Vect2D(0, 0)
        self._last_is_avoid: bool = False
        self._destination: Vect2D | None = None

    def on_avoid(self) -> Event[bool]:
        return self._avoid_event

    def start(self) -> None:
        self._running = True
        if self._thread is None:
            self._thread = Thread(target=self._avoid_loop)
            self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._thread.join()
            self._thread = None

    def disable(self) -> None:
        with self._lock:
            self._enabled = False
        self._logger.debug("Avoid disabled")

    def enable(self) -> None:
        with self._lock:
            if self._enabled:
                return
            self._enabled = True
        self._update_event.set()
        self._logger.debug("Avoid enabled")

    def set_destination(self, position: Vect2D) -> None:
        self._destination = position

    def _is_obstacle_valid(self, obstacle: Obstacle) -> bool:
        return True  # TODO: Check if obstacle is inside the table

    def feed_obstacles(self, obstacles: list[Obstacle]) -> None:
        with self._lock:
            self._obstacles.clear()
            for obstacle in obstacles:
                if self._is_obstacle_valid(obstacle):
                    self._obstacles.append(obstacle)
        self._update_event.set()

    def feed_robot_pose(self, pose: Pose2D, velocity: Vect2D) -> None:
        with self._lock:
            self._pose = pose
            self._velocity = velocity
        self._update_event.set()

    def _should_avoid(self) -> bool:
        # Trace a rectangle from the robot center in the direction of the velocity

        # v(t) = v(0) - deceleration * t
        # d(t) = integral(v(t))
        # d(t) = t * v(0) - deceleration * t^2 / 2
        # v(time_to_brake) = 0
        #   <=> v(0) - deceleration * time_to_brake = 0
        #   <=> time_to_brake = v(0) / deceleration
        # distance_to_brake = d(time_to_brake)

        velocity = self._velocity

        speed = velocity.norm()
        if speed < 1e-2:
            # If the robot is stopped, use the last non-null velocity to determine the direction of movement
            velocity = self._last_non_null_velocity
        else:
            self._last_non_null_velocity = velocity

        direction = velocity.normalized()
        orthogonal_direction = Vect2D(-direction.y, direction.x)

        time_to_brake = speed / self._parameters.deceleration
        distance_to_brake = time_to_brake * (
            speed - self._parameters.deceleration * time_to_brake / 2
        )

        rectangle_length = (
            self._parameters.rectangle_length
            + distance_to_brake
            + speed * self._parameters.latency
        )
        rectangle_width = self._parameters.rectangle_width

        with self._lock:
            obstacles = self._obstacles.copy()

        for obstacle in obstacles:
            obstacle_vector = obstacle.position - self._pose.position
            if abs(orthogonal_direction.dot(obstacle_vector)) > rectangle_width / 2:
                continue

            distance_before_collision = direction.dot(obstacle_vector)
            if (
                distance_before_collision < 0
                or distance_before_collision > rectangle_length
            ):
                continue

            self._logger.debug("Avoid detected")
            return True

        return False

    def should_avoid(self) -> bool:
        with self._lock:
            return self._last_is_avoid

    def _avoid_loop(self) -> None:
        while self._running:
            self._update_event.wait()

            with self._lock:
                if not self._running:
                    break

            self._update_event.clear()

            with self._lock:
                if not self._enabled:
                    continue

            avoid = self._should_avoid()

            with self._lock:
                _last_is_avoid = self._last_is_avoid
                self._last_is_avoid = avoid

            if avoid and not _last_is_avoid:
                self._avoid_event.trigger(True)
            elif not avoid and _last_is_avoid:
                self._avoid_event.trigger(False)
