from dataclasses import dataclass
from math import pi, sqrt
from threading import Lock, Thread

from evo_lib.event import Event
from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.interfaces.obstacles_provider import Obstacle, ObstacleProvider
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.pose import Pose2D
from evo_lib.types.vect import Vect2D


@dataclass(slots=True)
class LidarObstacle:
    """An obstacle relative to the lidar point of view"""

    min_angle: float
    max_angle: float
    min_distance: float
    max_distance: float
    center_angle: float
    nb_points: int
    lidar_pose: Pose2D


@dataclass
class LidarObstacleDetectorParameters:
    max_obstacle_angle: float = pi / 8  # Maximum size of an obstacle
    max_point_distances: float = 40  # Max distance between consecutive points of a same obstacle
    min_nb_points: int = 3  # Minimum number of points per obstacle
    min_turns: int = 1
    min_measure_quality: float = 0
    max_measure_distance: float = 1500
    min_measure_distance: float = 30


class LidarObstaclesDetector(ObstacleProvider):
    def __init__(self, logger: Logger, parameters: LidarObstacleDetectorParameters):
        self._lidar: Lidar2D | None = None
        self._logger = logger
        self._parameters = parameters
        self._previous_turns: list[list[Lidar2DMeasure]]
        self._current_turn: list[Lidar2DMeasure] = []
        self._last_measure_angle: float = 0
        self._last_delta_measure_angle: float = 0
        self._lidar_obstacles_event: Event[list[LidarObstacle]] = Event()
        self._obstacles_event: Event[list[Obstacle]] = Event()
        self._last_lidar_pose: Pose2D = Pose2D()
        self._lock = Lock()
        self._running: bool = False
        self._thread: Thread | None = None

    def init(self) -> Task[()]:
        self.start()
        return ImmediateResultTask()

    def close(self) -> None:
        self.stop()

    def get_on_obstacles(self) -> Event[list[Obstacle]]:
        return self._obstacles_event

    def set_lidar(self, lidar: Lidar2D) -> None:
        self._lidar = lidar

    def feed_lidar_pose(self, pose: Pose2D) -> None:
        with self._lock:
            self._last_lidar_pose = pose

    def _merge_two_turns(
        self, a: list[Lidar2DMeasure], b: list[Lidar2DMeasure]
    ) -> list[Lidar2DMeasure]:
        merged: list[Lidar2DMeasure] = []

        i = 0
        j = 0
        while i < len(a) and j < len(b):
            if a[i].angle < b[j].angle:
                merged.append(a[i])
                i += 1
            else:
                merged.append(b[j])
                j += 1

        while i < len(a):
            merged.append(a[i])
            i += 1

        while j < len(b):
            merged.append(b[j])
            j += 1

        return merged

    def _detect_obstacles(self, measures: list[Lidar2DMeasure]) -> list[LidarObstacle]:
        obstacles: list[LidarObstacle] = []
        current_obstacle: LidarObstacle | None = None
        merged_len = len(measures)
        i = 0
        while i < merged_len:
            c = measures[i]  # Current measure
            # For each measure, look 2 measurement ahead

            for j in range(1, 3):
                n = measures[(i + j) % merged_len]  # Measure looked ahead by 'j'
                # Compute distance between two measure in polar coordinate
                d = sqrt(
                    (c.distance - n.distance) ** 2
                    + ((c.angle - n.angle) * (c.distance + n.distance) * 0.5) ** 2
                )
                if d < self._parameters.max_point_distances:
                    # Point i + j can be connected to point i because it's close enough
                    if current_obstacle is None:
                        # Create new obstacle object if no current one exists
                        current_obstacle = LidarObstacle(
                            min_angle=c.angle,
                            max_angle=n.angle,
                            min_distance=c.distance,
                            max_distance=n.distance,
                            center_angle=(c.angle + n.angle) * 0.5,
                            nb_points=2,
                            lidar_pose=self._last_lidar_pose.copy(),
                        )
                    else:
                        # Append point to current obstacle object if obstacle is not too big
                        if (
                            abs(current_obstacle.center_angle - n.angle)
                            > self._parameters.max_obstacle_angle
                        ):
                            # Obstacle too big
                            if (
                                current_obstacle.nb_points
                                >= self._parameters.min_nb_points
                            ):
                                obstacles.append(current_obstacle)
                            current_obstacle = None
                            i += j
                            break

                        # Compute new min/max distance
                        if current_obstacle.min_distance > c.distance:
                            current_obstacle.min_distance = c.distance
                        if current_obstacle.max_distance < n.distance:
                            current_obstacle.max_distance = n.distance

                        # Compute new angle center (mean of obstacle's point angle) and increment number of points
                        current_obstacle.center_angle = (
                            (current_obstacle.center_angle * current_obstacle.nb_points)
                            + n.angle
                        ) / (current_obstacle.nb_points + 1)
                        current_obstacle.nb_points += 1

                    i += j
                    break
            else:  # If the above for loop has not been break
                # No following points can be connected to the current one
                if (
                    current_obstacle is not None
                    and current_obstacle.nb_points >= self._parameters.min_nb_points
                ):
                    obstacles.append(current_obstacle)
                current_obstacle = None
                i += 1

        # Append current obstacle to list of obstacles if obstacle is big enough
        if (
            current_obstacle is not None
            and current_obstacle.nb_points >= self._parameters.min_nb_points
        ):
            obstacles.append(current_obstacle)

        return obstacles

    def _detect_loop(self) -> None:
        assert self._lidar is not None

        for measure in self._lidar.iter():
            if not self._running:
                break

            # Filter points
            if (
                measure.quality < self._parameters.min_measure_quality
                or measure.distance < self._parameters.min_measure_distance
                or measure.distance > self._parameters.max_measure_distance
            ):
                continue

            measure.angle = measure.angle % (2 * pi)  # Normalize angle to [0, 2*pi]

            # Detect turns
            delta_measure_angle = measure.angle - self._last_measure_angle
            if delta_measure_angle * self._last_delta_measure_angle < 0:
                # New turn detected
                # Merge with previous turns
                merged = self._current_turn
                for turn in self._previous_turns:
                    merged = self._merge_two_turns(merged, turn)

                # Append current turn to previous turn and clear
                self._previous_turns.append(self._current_turn)
                if len(self._previous_turns) >= self._parameters.min_turns:
                    self._previous_turns.pop(0)
                self._current_turn = []

                # Detect obstacles and trigger lidar obstacles event
                lidar_obstacles = self._detect_obstacles(merged)
                self._lidar_obstacles_event.trigger(lidar_obstacles)

                # Convert to cartesian coordinates
                obstacles: list[Obstacle] = []
                for lidar_obstacle in lidar_obstacles:
                    lidar_obstacle_center = Vect2D.from_polar(
                        lidar_obstacle.min_distance, lidar_obstacle.center_angle
                    )
                    obstacle = Obstacle(
                        lidar_obstacle.lidar_pose.transform(lidar_obstacle_center)
                    )
                    # self._logger.info(f"Obstacle (lidar): {obstacle}")
                    obstacles.append(obstacle)

                # Trigger obstacles event
                self._obstacles_event.trigger(obstacles)

            self._current_turn.append(measure)
            self._last_measure_angle = measure.angle
            self._last_delta_measure_angle = delta_measure_angle

    def start(self) -> None:
        if self._lidar is None:
            raise ValueError("Lidar not set")
        self._running = True
        self._previous_turns = []
        self._current_turn = []
        self._thread = Thread(target=self._detect_loop)
        self._thread.start()
        self._logger.info("Lidar obstacles detector started")

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        self._logger.info("Lidar obstacles detector stopped")

    def on_obstacles(self) -> Event[list[Obstacle]]:
        return self._obstacles_event
