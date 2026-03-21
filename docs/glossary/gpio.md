# GPIO

A **GPIO** (General-Purpose Input/Output) represents a single digital I/O pin.

## Class: `GPIO`

**Module:** `evo_lib.interfaces.gpio`
**Extends:** [Component](component.md)
**Locatable:** No

| Method | Returns | Description |
|--------|---------|-------------|
| `read()` | [Task](task.md)\[bool\] | Read current pin state (True = high) |
| `write(state)` | [Task](task.md)\[None\] | Set output state (True = high) |
| `interrupt(edge)` | [Event](event.md)\[bool\] | Get an Event that triggers on the given edge |

### Interrupt

The `interrupt()` method returns an [Event](event.md) that fires every time the pin
transitions on the specified edge. The event value is the new pin state after the
transition.

## Enum: `GPIOEdge`

**Module:** `evo_lib.interfaces.gpio`

Specifies which transitions trigger an interrupt.

| Value | Description |
|-------|-------------|
| `RISING` | Low → High transition |
| `FALLING` | High → Low transition |
| `BOTH` | Any transition |

## Drivers

| Driver | Hardware | Bus |
|--------|----------|-----|
| `gpio` | Raspberry Pi native GPIO pins | RPi.GPIO |
| `mcp23017` | MCP23017 I2C 16-bit I/O expander | I2C |
| `pump` | Vacuum pump (on/off via GPIO) | GPIO |
| `magnet` | Electromagnet (on/off via GPIO) | GPIO |
| `proximity` | Proximity sensor (digital input) | GPIO |
| `recal` | Recalibration distance sensor | GPIO |

## See also

- [Component](component.md) — lifecycle base class
- [Event](event.md) — returned by `interrupt()`
- [AnalogInput](analog-input.md) — for voltage readings instead of digital state
