# Glossary

Reference documentation for every concept, class, and interface in `evo-hl-library`.

Each file documents a single concept. Files are self-contained but link to related
concepts when needed.

## Architecture

| Concept | File | Summary |
|---------|------|---------|
| [Component](component.md) | `component.md` | Lifecycle base class for all hardware devices |
| [Interface](interface.md) | `interface.md` | Abstract hardware contract (what a device can do) |
| [Driver](driver.md) | `driver.md` | Concrete implementation of an interface (talks to real hardware) |
| [Fake](fake.md) | `fake.md` | Simulation implementation of a driver (no hardware needed) |

## Concurrency

| Concept | File | Summary |
|---------|------|---------|
| [Task](task.md) | `task.md` | Asynchronous operation with progress, cancellation, and callbacks |
| [Event](event.md) | `event.md` | Multi-shot thread-safe notification (sensor triggers, interrupts) |
| [Listener](listener.md) | `listener.md` | Callback registry (base building block for Event) |

## Hardware Interfaces

| Interface | File | Locatable | Example hardware |
|-----------|------|-----------|-----------------|
| [GPIO](gpio.md) | `gpio.md` | No | RPi pin, MCP23017 pin |
| [Servo](servo.md) | `servo.md` | No | PCA9685 channel |
| [SmartServo](servo.md#smartservo) | `servo.md` | No | Dynamixel AX-12A |
| [Pilot](pilot.md) | `pilot.md` | Yes | Carte asserv (differential or holonomic) |
| [AnalogInput](analog-input.md) | `analog-input.md` | No | ADS1115 channel |
| [ColorSensor](color-sensor.md) | `color-sensor.md` | Yes | TCS34725 behind TCA9548A |
| [Lidar2D](lidar.md) | `lidar.md` | Yes | RPLidar A2, SICK TIM |
| [LedStrip](led-strip.md) | `led-strip.md` | No | WS2812B / NeoPixel |

> **Locatable** means the component has a physical position and orientation on the robot
> that matters for its function (e.g. a LiDAR mounted at a specific angle). Non-locatable
> components work identically regardless of where they sit on the robot.

## Types

| Type | File | Summary |
|------|------|---------|
| [Color](color.md) | `color.md` | RGBA value object (normalized floats) |
