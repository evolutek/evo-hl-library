# Color

A **Color** is an RGBC value object with normalized float channels.

## Class: `Color`

**Module:** `evo_lib.types.color`

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `r` | float | 0.0–1.0 | Red channel |
| `g` | float | 0.0–1.0 | Green channel |
| `b` | float | 0.0–1.0 | Blue channel |
| `c` | float | 0.0–1.0 | Clear / unfiltered channel (default: 1.0). Overall luminous intensity for RGBC sensors (TCS34725 family). NOT an alpha transparency. |

Uses `__slots__` for memory efficiency.

### Factory methods

| Method | Input | Description |
|--------|-------|-------------|
| `Color(r, g, b, c=1.0)` | Normalized floats | Direct construction |
| `Color.from_rgb_int(val)` | `0xRRGGBB` integer | Parse packed RGB (clear = 1.0) |
| `Color.from_rgbc_int(val)` | `0xRRGGBBCC` integer | Parse packed RGBC |

### Example

```python
red = Color(1.0, 0.0, 0.0)
blue = Color.from_rgb_int(0x0000FF)
```

## Used by

- [ColorSensor](../interfaces/color-sensor.md) — `read_color()` returns a Color (r/g/b clear-normalized, c = clear-channel intensity)
- [LedStrip](../interfaces/led-strip.md) — `set_pixel()` and `fill()` take a Color (c is ignored for RGB strips)
