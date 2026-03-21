# AnalogInput

An **AnalogInput** represents a single analog voltage input channel.

## Class: `AnalogInput`

**Module:** `evo_lib.interfaces.analog_input`
**Extends:** [Component](../architecture/component.md)

| Method | Returns | Description |
|--------|---------|-------------|
| `read_voltage()` | [Task](../concurrency/task.md)\[float\] | Read the current voltage (in volts) |

## Driver

| Driver | Hardware | Bus |
|--------|----------|-----|
| `ads1115` | ADS1115 16-bit 4-channel ADC | I2C (addr 0x48) |

Each channel of the ADS1115 is exposed as a separate AnalogInput [Component](../architecture/component.md). The ADS1115 driver itself may be a [ComponentHolder](../architecture/component.md#class-componentholder) that owns its channels.

## See also

- [Component](../architecture/component.md) — lifecycle base class
- [GPIO](gpio.md) — for digital (boolean) readings instead of voltage
