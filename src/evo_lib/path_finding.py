import heapq
import math
from abc import ABC, abstractmethod
from typing import Optional

import numpy as np
import shapely

from evo_lib.types.transform import Transform2D
from evo_lib.types.vect import Vect2D


class Path:
    def __init__(self):
        self.points: list[Vect2D] = []

    def add(self, p: Vect2D) -> None:
        self.points.append(p)


class Shape(ABC):
    @abstractmethod
    def convex_hull(self) -> "Shape":
        pass

    @abstractmethod
    def grow(self, padding: float) -> "Shape":
        pass

    @abstractmethod
    def get_nb_points(self) -> int:
        pass

    @abstractmethod
    def get_points(self) -> list[Vect2D]:
        pass

    @abstractmethod
    def transform(self, transform: Transform2D) -> None:
        pass

    @abstractmethod
    def is_line_crossing(self, p1: Vect2D, p2: Vect2D) -> bool:
        pass

    @abstractmethod
    def is_point_crossing(self, p: Vect2D) -> bool:
        pass

    @abstractmethod
    def get_centroid(self) -> Vect2D:
        pass

    @abstractmethod
    def find_visible_points_from(self, point_index: int) -> list[int]:
        pass

    @abstractmethod
    def find_outermost_points_from(self, pov: Vect2D) -> list[int]:
        pass

    # Compute heuristic of each point for a specific destination coordinates
    @abstractmethod
    def compute_heuristics(self, destination: Vect2D) -> list[float]:
        pass


class PolygoneShape(Shape):
    def __init__(self, points: list[Vect2D]):
        # The polygon need to have their point oriented counter-clockwise
        # because it's used by find_coutour_paths
        self.points = points
        self._update()

    def _update(self) -> None:
        self.polygone = shapely.Polygon([(v.x, v.y) for v in self.points])
        self.polygone = shapely.orient_polygons(self.polygone, exterior_cw=False)
        self.points = [Vect2D(x, y) for x, y in self.polygone.exterior.coords]

    def transform(self, transform: Transform2D) -> None:
        for point in self.points:
            transform.apply_to_point(point)
        self._update()

    def get_nb_points(self) -> int:
        return len(self.points)

    def get_points(self) -> list[Vect2D]:
        return self.points

    def convex_hull(self) -> "PolygoneShape":
        return PolygoneShape([Vect2D(*c) for c in self.polygone.convex_hull.exterior.coords])

    def grow(self, padding: float) -> "PolygoneShape":
        return PolygoneShape([Vect2D(*c) for c in self.polygone.buffer(padding).exterior.coords])

    def is_line_crossing(self, p1: Vect2D, p2: Vect2D) -> bool:
        line = shapely.LineString([(p1.x, p1.y), (p2.x, p2.y)])
        return bool(shapely.intersects(self.polygone, line))

    def is_point_crossing(self, p: Vect2D) -> bool:
        return bool(shapely.contains_xy(self.polygone, p.x, p.y))

    def get_centroid(self) -> Vect2D:
        c = self.polygone.centroid
        return Vect2D(c.x, c.y)

    def find_visible_points_from(self, point_index: int) -> list[int]:
        nb_points = len(self.points)
        return [(point_index - 1) % nb_points, (point_index + 1) % nb_points]

    def find_outermost_points_from(self, pov: Vect2D) -> list[int]:
        # TODO: Handle non convex polygone when "pov" is inside the convex hull of the polygone

        points = self.points
        nb_points = len(points)

        best_left_point = points[0]
        best_left_point_index = 0

        best_right_point = points[1]
        best_right_point_index = 1

        best_left_point_direction = (best_left_point - pov).normalized()

        best_separation_score = best_left_point_direction.dot((best_right_point - pov).normalized())

        for i in range(2, nb_points):
            p = points[i]
            separation_score = best_left_point_direction.dot((p - pov).normalized())
            if separation_score < best_separation_score:
                best_separation_score = separation_score
                best_right_point = p
                best_right_point_index = i

        best_right_point_direction = (best_right_point - pov).normalized()

        for i in range(0, nb_points):
            p = points[i]
            separation_score = (p - pov).normalized().dot(best_right_point_direction)
            if separation_score < best_separation_score:
                best_separation_score = separation_score
                best_left_point = p
                best_left_point_index = i

        # Ensure that best_left_point is left point from destination POV

        if (best_left_point - pov).cross(best_right_point - pov) > 0:
            best_left_point, best_right_point = best_right_point, best_left_point
            best_left_point_index, best_right_point_index = (
                best_right_point_index,
                best_left_point_index,
            )

        return [best_left_point_index, best_right_point_index]

    def find_go_arround_paths(self, origin: Vect2D, destination: Vect2D) -> tuple[Path, Path]:
        points = list(self.polygone.exterior.coords)

        # Find left most and right most vertice from the destination POV
        best_left_point_index_1, best_right_point_index_1, _, _ = self.find_outermost_points_from(
            destination
        )

        # Find left most and right most vertice from the origin POV
        best_left_point_index_2, best_right_point_index_2, _, _ = self.find_outermost_points_from(
            origin
        )

        left_path = Path()
        right_path = Path()

        left_path.add(origin)
        right_path.add(origin)

        i = best_left_point_index_1
        while i != best_left_point_index_2:
            left_path.add(points[i])
            i = (i - 1) % len(points)
        left_path.add(best_left_point_index_2)

        i = best_right_point_index_1
        while i != best_right_point_index_2:
            right_path.add(points[i])
            i = (i + 1) % len(points)
        right_path.add(best_right_point_index_2)

        left_path.add(destination)
        right_path.add(destination)

        return (left_path, right_path)

    # Compute heuristic of each point for a specific destination coordinates
    def compute_heuristics(self, destination: Vect2D) -> list[float]:
        points = self.points
        nb_points = len(points)

        # return [point.distance(destination) for point in points]

        # Find left most and right most point from the destination POV
        [best_left_point_index, best_right_point_index] = self.find_outermost_points_from(
            destination
        )
        best_left_point = points[best_left_point_index]
        best_right_point = points[best_right_point_index]

        heuristics = [math.inf] * nb_points

        # Compute heuristics of points visible from destination

        i = best_left_point_index
        while i != best_right_point_index:
            heuristics[i] = points[i].distance(destination)
            i = (i + 1) % nb_points
        heuristics[i] = points[i].distance(destination)

        # Compute heuristics of points not directly visible from destination

        i = (best_left_point_index - 1) % nb_points
        previous_point = best_left_point
        accumulated_length = best_left_point.distance(destination)
        while i != best_right_point_index:
            current_point = points[i]
            accumulated_length += previous_point.distance(current_point)
            previous_point = current_point
            heuristics[i] = min(heuristics[i], accumulated_length)
            i = (i - 1) % nb_points

        i = (best_right_point_index + 1) % nb_points
        previous_point = best_right_point
        accumulated_length = best_right_point.distance(destination)
        while i != best_left_point_index:
            current_point = points[i]
            accumulated_length += previous_point.distance(current_point)
            previous_point = current_point
            heuristics[i] = min(heuristics[i], accumulated_length)
            i = (i + 1) % nb_points

        return heuristics


class BorderPolygoneShape(PolygoneShape):
    def __init__(self, points: list[Vect2D]):
        super().__init__(points)

    def is_line_crossing(self, p1: Vect2D, p2: Vect2D) -> bool:
        line = shapely.LineString([(p1.x, p1.y), (p2.x, p2.y)])
        return not shapely.contains(self.polygone, line)

    def is_point_crossing(self, p: Vect2D) -> bool:
        return not shapely.contains_xy(self.polygone, p.x, p.y)

    def find_visible_points_from(self, point_index: int) -> list[int]:
        nb_points = len(self.points)

        last_i = (point_index - 1) % nb_points
        visibles: list[int] = [(point_index + 1) % nb_points, last_i]

        i = (point_index + 2) % nb_points
        while i != last_i:
            p1 = self.points[point_index]
            p2 = self.points[i]

            direction = (p2 - p1).normalized() * 0.001
            p1 = p1 + direction
            p2 = p2 - direction

            if not self.is_line_crossing(p1, p2):
                visibles.append(i)

            i = (i + 1) % nb_points

        return visibles

    def find_outermost_points(self, pov: Vect2D) -> list[int]:
        # TODO: Filter only usefull points from the border shape ?
        return list(range(len(self.points)))

    # Compute heuristic of each point for a specific destination coordinates
    def compute_heuristics(self, destination: Vect2D) -> list[float]:
        points: list[Vect2D] = [Vect2D(x, y) for x, y in self.polygone.exterior.coords]
        return [point.distance(destination) for point in points]


class PathFindingMap:
    def __init__(self):
        self.shapes: list[Shape] = []
        self.border_shape: Shape | None = None

    def add_shape(self, polygone: Shape) -> None:
        self.shapes.append(polygone)

    def has_clear_line_of_sight(
        self,
        shapes: list[Shape],
        p1: Vect2D,
        p2: Vect2D,
        shrink: float = 0,
        shape_index_to_ignore: int = -1,
    ) -> bool:
        if p1 == p2:
            return True

        # Offset a little p1 and p2 to avoid colliding with self polygon
        if shrink != 0:
            direction = (p2 - p1).normalized() * shrink
            p1 = p1 + direction
            p2 = p2 - direction

        for shape_index, shape in enumerate(shapes):
            if shape_index == shape_index_to_ignore:
                continue
            if shape.is_line_crossing(p1, p2):
                return False

        return True

    def find(self, origin: Vect2D, destination: Vect2D) -> Optional[Path]:
        return self.find_optimized(origin, destination)

    def find_optimized(self, origin: Vect2D, destination: Vect2D) -> Optional[Path]:
        points: list[Vect2D] = []

        assert self.border_shape is not None
        shapes = self.shapes + [self.border_shape]

        # Ensure that that origin and destination are reachable
        for shape in shapes:
            if shape.is_point_crossing(origin) or shape.is_point_crossing(destination):
                return None

        nb_points = sum((shape.get_nb_points() for shape in shapes)) + 2
        nb_shapes = len(shapes)

        # print(f"Number of points: {nb_points}")

        heuristics = np.zeros(shape=(nb_points), dtype=np.float32)

        shapes_start_index = np.zeros(shape=(nb_shapes), dtype=np.int32)
        shape_index_of_points = np.zeros(shape=(nb_points), dtype=np.int32)

        # Compute heuristics for each points of each shapes

        for shape_index, shape in enumerate(shapes):
            i = len(points)
            shapes_start_index[shape_index] = i
            shape_points = shape.get_points()
            points.extend(shape_points)
            for heuristic in shape.compute_heuristics(destination):
                heuristics[i] = heuristic
                shape_index_of_points[i] = shape_index
                i += 1

        origin_index = nb_points - 2
        destination_index = nb_points - 1

        points.append(origin)
        points.append(destination)

        shape_index_of_points[origin_index] = -2
        shape_index_of_points[destination_index] = -1

        heuristics[origin_index] = origin.distance(destination)
        heuristics[destination_index] = 0

        # A* algorithme with on the fly smart visibility graph building

        # distances = np.array([math.inf] * nb_points, dtype = np.float32)
        # distances[origin_index] = 0

        previous = np.zeros(shape=(nb_points), dtype=np.int32)
        previous[origin_index] = -1
        previous[destination_index] = -1

        visiteds = np.zeros(shape=(nb_points), dtype=bool)

        queue: list[tuple[float, int, int]] = []
        heapq.heappush(queue, (heuristics[origin_index], origin_index, -1))

        # Stats
        nb_line_of_sign_checks = 0
        max_heap_size = 0

        while len(queue) > 0:
            max_heap_size = max(max_heap_size, len(queue))

            score, current_point_index, previous_point_index = heapq.heappop(queue)
            current_distance = score - heuristics[current_point_index]

            if visiteds[current_point_index]:
                continue

            current_point = points[current_point_index]
            current_shape_index = shape_index_of_points[current_point_index]

            if previous_point_index != -1:
                if current_shape_index != shape_index_of_points[previous_point_index]:
                    nb_line_of_sign_checks += 1
                    if not self.has_clear_line_of_sight(
                        shapes, points[previous_point_index], current_point, 0.001
                    ):
                        continue

                # The else below can be removed if their is no overlapping polygones
                else:
                    nb_line_of_sign_checks += 1
                    if not self.has_clear_line_of_sight(
                        shapes,
                        points[previous_point_index],
                        current_point,
                        0.001,
                        current_shape_index,
                    ):
                        continue

                previous[current_point_index] = previous_point_index

            visiteds[current_point_index] = True
            # distances[current_point_index] = current_distance + current_point.distance(destination)

            if current_point_index == destination_index:
                break

            for shape_index, shape in enumerate(shapes):
                if shape_index == current_shape_index:
                    continue

                outermost_points_index = shape.find_outermost_points_from(current_point)
                shape_start_index = shapes_start_index[shape_index]

                for outermost_point_index in outermost_points_index:
                    outermost_point_index += shape_start_index
                    if not visiteds[outermost_point_index]:
                        d = current_distance + current_point.distance(points[outermost_point_index])
                        heapq.heappush(
                            queue,
                            (
                                d + heuristics[outermost_point_index],
                                outermost_point_index,
                                current_point_index,
                            ),
                        )

            if current_shape_index >= 0:
                nexts = shapes[current_shape_index].find_visible_points_from(
                    current_point_index - shapes_start_index[current_shape_index]
                )
                shape_start_index = shapes_start_index[current_shape_index]

                for next_index in nexts:
                    next_index += shape_start_index
                    if not visiteds[next_index]:
                        d = current_distance + current_point.distance(points[next_index])
                        heapq.heappush(
                            queue, (d + heuristics[next_index], next_index, current_point_index)
                        )

            heapq.heappush(
                queue,
                (
                    current_distance + current_point.distance(destination),
                    destination_index,
                    current_point_index,
                ),
            )

        # print(f"Line of sight check done: {int(nb_line_of_sign_checks / (nb_points * nb_points) * 100 + 0.5)}% ({nb_line_of_sign_checks})")
        # print(f"Maximum reached min-heap size: {max_heap_size}")

        # Check if a path has been found

        if previous[destination_index] == -1:
            return None

        # Build path from the "previous" array

        path = Path()
        path.add(destination)
        i = destination_index
        while previous[i] != -1:
            i = previous[i]
            path.add(points[i])
        path.points.reverse()

        return path

    def find_simple(self, origin: Vect2D, destination: Vect2D) -> Optional[Path]:
        nb_points = sum((shape.get_nb_points() for shape in self.shapes)) + 2

        nexts: list[list[int]] = [[] for _ in range(nb_points)]
        points: list[tuple[Vect2D, Shape | None]] = []

        assert self.border_shape is not None
        shapes = self.shapes + [self.border_shape]

        # Generate visibility graph

        # Link points on the same shape (and add points to list)
        i = 0
        for shape in self.shapes:
            first_shape_point_index = i
            for point in shape.get_points():
                points.append((point, shape))
                if i != first_shape_point_index:
                    nexts[i].append(i - 1)
                    nexts[i - 1].append(i)
                i += 1
            # Link last to first shape point
            nexts[first_shape_point_index].append(i - 1)
            nexts[i - 1].append(first_shape_point_index)

        points.append((origin, None))
        points.append((destination, None))

        # Link points between shapes
        for i1, (p1, s1) in enumerate(points):
            for i2, (p2, s2) in enumerate(points):
                if s1 is not None and s1 is s2:
                    continue
                if self.has_clear_line_of_sight(shapes, p1, p2, 0.000001, i1):
                    nexts[i1].append(i2)
                    nexts[i2].append(i1)

        # Dijkstra on graph to find best path

        origin_index = nb_points - 2
        destination_index = nb_points - 1

        previous = np.zeros(shape=(nb_points), dtype=np.int32)
        previous[origin_index] = -1
        previous[destination_index] = -1

        queue: list[tuple[float, int]] = []
        heapq.heappush(queue, (0, destination_index))

        visiteds = np.zeros(shape=(nb_points), dtype=bool)
        visiteds[destination_index] = True

        found = False
        while len(queue) > 0 or found:
            score, i = heapq.heappop(queue)
            p1, _ = points[i]
            for next in nexts[i]:
                if visiteds[i]:
                    continue
                visiteds[i] = True

                previous[next] = i

                if next == origin_index:
                    found = True
                    break

                p2, _ = points[next]
                heapq.heappush(queue, (score + p1.distance(p2), next))

        # Check if a path has been found
        if previous[origin_index] == -1:
            return None

        # Compute path
        path = Path()
        path.add(origin)
        i = origin_index
        while previous[i] != -1:
            path.add(points[i][0])

        return path
