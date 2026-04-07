# ColorSensor

A **ColorSensor** reads RGB color values from a surface or object.

## Class: `ColorSensor`

**Module:** `evo_lib.interfaces.color_sensor`
**Extends:** [Placable](../architecture/peripheral.md#placable)

| Method | Returns | Description |
|--------|---------|-------------|
| `read_color()` | [Task](../concurrency/task.md)\[[Color](../types/color.md)\] | Read the current color |
| `calibrate(power, min, max)` | None | Set LED power and color range thresholds |

### Calibration

`calibrate()` configures the sensor's built-in LED brightness and the expected color range for normalization. This is called once at startup, not during operation.

## Driver

| Driver | Hardware | Bus |
|--------|----------|-----|
| `tca9548a` | TCS34725 RGB sensor behind TCA9548A I2C multiplexer | I2C (mux 0x70) |

Multiple color sensors share the same I2C address (TCS34725 = 0x29). The TCA9548A multiplexer selects which sensor is active. Each sensor is exposed as a separate ColorSensor Peripheral; the mux driver is an [InterfaceHolder](../architecture/peripheral.md#interfaceholder).

## See also

- [Color](../types/color.md) — the RGBA value object returned by `read_color()`
- [Peripheral hierarchy](../architecture/peripheral.md) — base classes
