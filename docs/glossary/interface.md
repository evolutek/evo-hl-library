# Interface

An **Interface** is an abstract class that defines what a category of hardware can do,
without knowing how.

## Purpose

Robot code (omnissiah) depends on interfaces, never on concrete [drivers](driver.md).
This makes it possible to:

- Swap real hardware for [fakes](fake.md) during testing
- Change the underlying hardware (e.g. PCA9685 → direct PWM) without touching robot logic
- Support multiple hardware revisions with a single codebase

## How interfaces work

Every interface:

1. Inherits from [Component](component.md) (lifecycle: `init` / `close`)
2. Declares abstract methods that return [Task](task.md) or [Event](event.md)
3. Lives in `src/evo_lib/interfaces/`

```
evo_lib/interfaces/
├── __init__.py          # Re-exports all interfaces
├── gpio.py              # GPIO, GPIOEdge
├── servo.py             # Servo
├── smart_servo.py       # SmartServo
├── pilot.py             # Pilot, DifferentialPilot, HolonomicPilot
├── analog_input.py      # AnalogInput
├── color_sensor.py      # ColorSensor
├── lidar.py             # Lidar2D, Lidar2DMeasure
└── led_strip.py         # LedStrip
```

## Interface catalog

| Interface | Extends | Locatable | Description |
|-----------|---------|-----------|-------------|
| [GPIO](gpio.md) | Component | No | Digital I/O pin |
| [Servo](servo.md) | Component | No | Angle-controlled servo (fire-and-forget PWM) |
| [SmartServo](servo.md#smartservo) | Servo | No | Servo with position feedback (e.g. AX-12) |
| [Pilot](pilot.md) | Component | Yes | Robot movement controller |
| [AnalogInput](analog-input.md) | Component | No | Analog voltage input channel |
| [ColorSensor](color-sensor.md) | Component | Yes | RGB color sensor |
| [Lidar2D](lidar.md) | Component | Yes | 2D scanning lidar |
| [LedStrip](led-strip.md) | Component | No | Addressable RGB LED strip |

## Return types convention

Interface methods never return raw values. They return:

- **[Task\[T\]](task.md)** for one-shot operations (read a value, move to a position)
- **[Event\[T\]](event.md)** for recurring notifications (interrupt trigger, scan complete)

This allows the caller to wait synchronously, register callbacks, or cancel the operation.

## See also

- [Component](component.md) — the base class all interfaces inherit from
- [Driver](driver.md) — concrete implementations of interfaces
- [Task](task.md) / [Event](event.md) — the return types used by interface methods
