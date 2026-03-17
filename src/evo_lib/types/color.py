class Color:
    __slots__ = ("r", "g", "b", "a")

    def __init__(self, r: float, g: float, b: float, a: float = 1.0) -> None:
        self.r = r
        self.g = g
        self.b = b
        self.a = a

    @staticmethod
    def from_rgb_int(val: int) -> "Color":
        r = (val >> 16) & 0xFF
        g = (val >>  8) & 0xFF
        b = (val      ) & 0xFF
        return Color(r / 255.0, g / 255.0, b / 255.0)

    @staticmethod
    def from_rgba_int(val: int) -> "Color":
        r = (val >> 24) & 0xFF
        g = (val >> 16) & 0xFF
        b = (val >>  8) & 0xFF
        a = (val      ) & 0xFF
        return Color(r / 255.0, g / 255.0, b / 255.0, a / 255.0)
