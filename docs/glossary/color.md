# Color

A **Color** is an RGBA value object with normalized float channels.

## Class: `Color`

**Module:** `evo_lib.types.color`

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `r` | float | 0.0–1.0 | Red channel |
| `g` | float | 0.0–1.0 | Green channel |
| `b` | float | 0.0–1.0 | Blue channel |
| `a` | float | 0.0–1.0 | Alpha channel (default: 1.0) |

Uses `__slots__` for memory efficiency.

### Factory methods

| Method | Input | Description |
|--------|-------|-------------|
| `Color(r, g, b, a=1.0)` | Normalized floats | Direct construction |
| `Color.from_rgb_int(val)` | `0xRRGGBB` integer | Parse packed RGB (alpha = 1.0) |
| `Color.from_rgba_int(val)` | `0xRRGGBBAA` integer | Parse packed RGBA |

### Example

```python
red = Color(1.0, 0.0, 0.0)
blue = Color.from_rgb_int(0x0000FF)
```

## Used by

- [ColorSensor](color-sensor.md) — `read_color()` returns a Color
- [LedStrip](led-strip.md) — `set_pixel()` and `fill()` take a Color
