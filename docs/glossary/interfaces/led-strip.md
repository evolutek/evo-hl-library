# LedStrip

A **LedStrip** is an addressable RGB LED strip where each pixel can be set individually.

## Class: `LedStrip`

**Module:** `evo_lib.interfaces.led_strip`
**Extends:** [Placable](../architecture/peripheral.md#placable)

| Method | Returns | Description |
|--------|---------|-------------|
| `set_pixel(index, color)` | None | Set a single pixel color (buffered) |
| `get_pixel(index)` | [Color](../types/color.md) | Get the current pixel color from the buffer |
| `fill(color)` | None | Set all pixels to the same color (buffered) |
| `set_brightness(brightness)` | None | Set global brightness (0.0–1.0) |
| `get_brightness()` | float | Get current global brightness |
| `show()` | [Task](../concurrency/task.md)\[None\] | Push the pixel buffer to the hardware |
| `clear()` | [Task](../concurrency/task.md)\[None\] | Turn off all pixels and show immediately |
| `num_pixels` | int (property) | Number of pixels in the strip |

### Double-buffered

`set_pixel()` and `fill()` modify an internal buffer without touching the hardware.
Call `show()` to push all changes at once. This avoids visible flickering during updates.

## Driver

| Driver | Hardware | Bus |
|--------|----------|-----|
| `ws2812b` | WS2812B / NeoPixel addressable LEDs | SPI or PWM |

## See also

- [Color](../types/color.md) — the RGBA value object used for pixel colors
- [Peripheral hierarchy](../architecture/peripheral.md) — base classes
