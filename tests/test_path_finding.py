import math
import random
import tkinter as tk

from evo_lib.path_finding import BorderPolygoneShape, Path, PathFindingMap, PolygoneShape
from evo_lib.types.transform import RigidTransform2D, Transform2D
from evo_lib.types.vect import Vect2D

SEED = 1234

WINDOW_HEIGHT = 600
WINDOW_WIDTH = 800

MIN_SHAPE_SIZE = 20
MAX_SHAPE_SIZE = 100

FPS = 30

NB_SHAPES = 30
MAX_POINTS_PER_POLYGONE = 6

BORDER_SHAPE = BorderPolygoneShape(
    [
        Vect2D(10, 10),
        Vect2D(WINDOW_WIDTH - 10, 10),
        Vect2D(WINDOW_WIDTH - 10, WINDOW_HEIGHT - 10),
        Vect2D(WINDOW_WIDTH - 10 - 200, WINDOW_HEIGHT - 10),
        Vect2D(WINDOW_WIDTH - 10 - 200, WINDOW_HEIGHT - 10 - 100),
        Vect2D(10 + 200, WINDOW_HEIGHT - 10 - 100),
        Vect2D(10 + 200, WINDOW_HEIGHT - 10),
        Vect2D(10, WINDOW_HEIGHT - 10),
    ]
)


def random_real(min: float, max: float) -> float:
    return random.random() * (max - min) + min


def random_polygone(
    min_x: float, max_x: float, min_y: float, max_y: float, n: int = MAX_POINTS_PER_POLYGONE
) -> PolygoneShape:
    vertices: list[Vect2D] = []
    for _ in range(n):
        x = random_real(min_x, max_x)
        y = random_real(min_y, max_y)
        vertices.append(Vect2D(x, y))
    return PolygoneShape(vertices).convex_hull()


def random_transform() -> Transform2D:
    return RigidTransform2D.create_rotate_then_translate(
        math.pi * 2 * random.random(),
        Vect2D(
            random_real(MIN_SHAPE_SIZE, WINDOW_WIDTH - MIN_SHAPE_SIZE),
            random_real(MIN_SHAPE_SIZE, WINDOW_HEIGHT - MIN_SHAPE_SIZE),
        ),
    )


def draw_polygone(
    canvas: tk.Canvas, polygone: PolygoneShape, fill: str | None = None, outline: str | None = None
) -> list[int]:
    points = polygone.get_points()
    args = []
    for point in points:
        args.append(point.x)
        args.append(point.y)
    id = canvas.create_polygon(*args, fill=fill, outline=outline)
    return [id]


def draw_path(canvas: tk.Canvas, path: Path) -> list[int]:
    ids: list[int] = []
    for i in range(1, len(path.points)):
        p1 = path.points[i - 1]
        p2 = path.points[i]
        id = canvas.create_line(p1.x, p1.y, p2.x, p2.y, fill="#FF0000")
        ids.append(id)
    return ids


class Test:
    __test__ = False  # Do not run pytest on this class

    def __init__(self) -> None:
        self.origin = Vect2D(0, 0)
        self.destination = Vect2D(0, 0)

        self.need_update = True

        self.polygones: list[PolygoneShape] = []

    def update_origin(self, event) -> None:
        # print(f"Update origin")
        self.origin = Vect2D(event.x, event.y)
        self.need_update = True

    def update_destination(self, event) -> None:
        # print(f"Update destination")
        self.destination = Vect2D(event.x, event.y)
        self.need_update = True

    def on_motion(self, event) -> None:
        # print(event.state)
        if event.state & 0x0100:  # Button1Mask
            self.update_origin(event)
        elif event.state & 0x0400:  # Button3Mask
            self.update_destination(event)

    def loop(self) -> None:
        self.window.after(1000 // FPS, self.loop)

        if not self.need_update:
            return
        self.need_update = False
        # print("Updating", flush = True)
        path = self.map.find(self.origin, self.destination)

        self.canvas.delete("all")

        for polygone in self.polygones:
            draw_polygone(self.canvas, polygone, fill="#888888", outline="#424242")

        draw_polygone(self.canvas, BORDER_SHAPE, fill="", outline="#000000")

        if path is not None:
            draw_path(self.canvas, path)

    def main(self):
        random.seed(SEED)

        self.window = tk.Tk()

        self.window.title("Path Finding")
        self.window.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")

        self.map = PathFindingMap()
        self.map.border_shape = BORDER_SHAPE

        for _ in range(NB_SHAPES):
            size = random.random() ** 2 * (MAX_SHAPE_SIZE - MIN_SHAPE_SIZE) + MIN_SHAPE_SIZE
            shape = random_polygone(-size, size, -size, size)
            shape.transform(random_transform())
            self.map.add_shape(shape)
            self.polygones.append(shape)

        self.canvas = tk.Canvas(self.window, bg="#FFFFFF", width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
        self.canvas.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Button-1>", self.update_origin)
        self.canvas.bind("<Button-3>", self.update_destination)

        self.loop()
        self.window.mainloop()


if __name__ == "__main__":
    Test().main()
