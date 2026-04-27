# LedStrip

A **LedStrip** is an addressable RGB LED strip where each pixel can be set individually.

## Class: `LedStrip`

**Module:** `evo_lib.interfaces.led_strip`
**Extends:** [Placable](../architecture/peripheral.md#placable)

| Method | Returns | Description |
|--------|---------|-------------|
| `set_pixel(index, r, g, b)` | [Task](../concurrency/task.md)\[None\] | Buffer one pixel (RGB floats 0.0–1.0) |
| `get_pixel(index)` | [Task](../concurrency/task.md)\[float, float, float\] | Read the buffered RGB triplet |
| `fill(r, g, b)` | [Task](../concurrency/task.md)\[None\] | Buffer the same color into every pixel |
| `set_brightness(brightness)` | [Task](../concurrency/task.md)\[None\] | Set global brightness (0.0–1.0) |
| `get_brightness()` | [Task](../concurrency/task.md)\[float\] | Get current global brightness |
| `show()` | [Task](../concurrency/task.md)\[None\] | Push the pixel buffer to the hardware |
| `clear()` | [Task](../concurrency/task.md)\[None\] | Buffer black on every pixel and `show` immediately |
| `num_pixels` | int (property) | Number of pixels in the strip |

### Double-buffered

`set_pixel()` and `fill()` modify an internal buffer without touching the hardware.
Call `show()` to push all changes at once. This avoids visible flickering during
multi-pixel updates.

### Color encoding

The interface takes RGB primitives (three floats in 0.0–1.0) rather than a
[Color](../types/color.md) struct because the underlying command system
serializes scalar fields, not arbitrary objects. The Color type's fourth
"clear" channel has no LED meaning and is intentionally absent.

## Drivers

| Driver | Hardware | Bus / Strategy |
|--------|----------|----------------|
| [WS2812B](../drivers/ws2812b.md) | WS2812B / NeoPixel addressable LEDs | DMA via PWM (GPIO 12/18), PCM (21), or SPI (10) |

A `WS2812BVirtual` twin with bit-exact buffer semantics is provided in the
same module for tests and simulation.

## See also

- [Color](../types/color.md) — the RGBC value object used for sensor-side reads
- [Peripheral hierarchy](../architecture/peripheral.md) — base classes
