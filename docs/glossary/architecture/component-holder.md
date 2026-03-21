# ComponentHolder

A **ComponentHolder** is a [Component](component.md) that owns and manages other Components. It models the composition pattern: one logical device made of several sub-devices.

## Class: `ComponentHolder`

**Module:** `evo_lib.component`
**Extends:** [Component](component.md)

```python
class ComponentHolder(Component):
    @abstractmethod
    def get_subcomponents(self) -> list[Component]: ...
```

| Member | Description |
|--------|-------------|
| `get_subcomponents()` | Return the list of child Components managed by this holder |

Inherits `init()`, `close()`, and `name` from Component.

## When to use

Use ComponentHolder when a single hardware chip exposes multiple independent channels, each of which is a Component in its own right.

| Holder | Children | Why |
|--------|----------|-----|
| TCA9548A mux driver | One [ColorSensor](../interfaces/color-sensor.md) per channel | 8 sensors share one I2C address; the mux selects which is active |
| ADS1115 driver | One [AnalogInput](../interfaces/analog-input.md) per channel | 4 ADC channels on one chip |
| MCP23017 driver | One [GPIO](../interfaces/gpio.md) per pin | 16 GPIO pins on one I2C expander |
| PCA9685 driver | One [Servo](../interfaces/servo.md) per channel | 16 PWM channels on one chip |

## Lifecycle responsibility

The holder is responsible for initializing and closing its children in the correct order:

1. `init()` — the holder opens the bus, then initializes each child
2. `close()` — the holder closes each child, then releases the bus

This ensures that children never outlive their parent's bus connection.

## Relationship with config

In `assemblies.json5`, a holder typically appears as a board-level entry, and its children are the individual channels or pins mapped under it.

## See also

- [Component](component.md) — the base class ComponentHolder extends
- [Driver](driver.md) — holders are a type of driver (they talk to hardware)
- [Interface](interface.md) — children implement hardware interfaces
