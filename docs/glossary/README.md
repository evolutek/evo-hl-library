# Glossary

Reference documentation for every concept, class, and interface in `evo-hl-library`.

Each file documents a single concept. Files are self-contained but link to related concepts when needed.

## Architecture

| Concept | File | Summary |
|---------|------|---------|
| [Component](architecture/component.md) | `architecture/component.md` | Lifecycle base class for all hardware devices |
| [ComponentHolder](architecture/component-holder.md) | `architecture/component-holder.md` | Component that owns and manages other Components |
| [Interface](architecture/interface.md) | `architecture/interface.md` | Abstract hardware contract (what a device can do) |
| [Driver](architecture/driver.md) | `architecture/driver.md` | Concrete implementation of an interface (talks to real hardware) |
| [Fake](architecture/fake.md) | `architecture/fake.md` | Simulation implementation of a driver (no hardware needed) |

## Concurrency

| Concept | File | Summary |
|---------|------|---------|
| [Task](concurrency/task.md) | `concurrency/task.md` | Asynchronous operation with progress, cancellation, and callbacks |
| [Event](concurrency/event.md) | `concurrency/event.md` | Multi-shot thread-safe notification (sensor triggers, interrupts) |
| [Listener](concurrency/listener.md) | `concurrency/listener.md` | Callback registry (base building block for Event) |

## Hardware Interfaces

| Interface | File | Example hardware |
|-----------|------|-----------------|
| [GPIO](interfaces/gpio.md) | `interfaces/gpio.md` | RPi pin, MCP23017 pin |
| [Servo](interfaces/servo.md) | `interfaces/servo.md` | PCA9685 channel |
| [SmartServo](interfaces/servo.md#smartservo) | `interfaces/servo.md` | Dynamixel AX-12A |
| [Pilot](interfaces/pilot.md) | `interfaces/pilot.md` | Carte asserv (differential or holonomic) |
| [AnalogInput](interfaces/analog-input.md) | `interfaces/analog-input.md` | ADS1115 channel |
| [ColorSensor](interfaces/color-sensor.md) | `interfaces/color-sensor.md` | TCS34725 behind TCA9548A |
| [Lidar2D](interfaces/lidar.md) | `interfaces/lidar.md` | RPLidar A2, SICK TIM |
| [LedStrip](interfaces/led-strip.md) | `interfaces/led-strip.md` | WS2812B / NeoPixel |

## Types

| Type | File | Summary |
|------|------|---------|
| [Color](types/color.md) | `types/color.md` | RGBA value object (normalized floats) |
