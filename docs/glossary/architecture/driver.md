# Driver

A **Driver** is a concrete implementation of a [Placable or Interface](peripheral.md) contract. It translates abstract operations (read a voltage, move to an angle) into hardware-specific protocol calls (I2C register writes, serial packets, SPI transfers).

## Purpose

Drivers are the only place in the codebase that knows about specific hardware protocols.
Everything above (robot logic, action sequences, strategy) works exclusively through interfaces.

## Module structure

Each driver follows a standard layout:

```
evo_lib/drivers/<name>/
├── base.py       # Abstract base (often just re-exports the interface)
├── rpi.py        # Real implementation for Raspberry Pi
├── fake.py       # Simulation implementation (see Fake)
├── factory.py    # create(config) → concrete instance
├── config.py     # Pydantic model for this driver's configuration
└── __init__.py   # Public API re-exports
```

| File | Role |
|------|------|
| `base.py` | Re-exports or extends the [Placable/Interface](peripheral.md) with driver-specific details |
| `rpi.py` | Real implementation using hardware libraries (smbus2, pyserial, RPi.GPIO, etc.) |
| `fake.py` | [Fake](fake.md) implementation for testing without hardware |
| `factory.py` | Factory function that reads config and returns the right implementation |
| `config.py` | Pydantic v2 model that validates driver-specific configuration fields |

## Driver catalog

| Driver | Interface | Bus/Protocol | Hardware |
|--------|-----------|-------------|----------|
| `gpio` | [GPIO](../interfaces/gpio.md) | RPi.GPIO / MCP23017 I2C | Digital pins |
| `pca9685` | [Servo](../interfaces/servo.md) | I2C | PCA9685 PWM controller |
| `ax12` | [SmartServo](../interfaces/servo.md#smartservo) | Serial (USB2AX) | Dynamixel AX-12A |
| `ads1115` | [AnalogInput](../interfaces/analog-input.md) | I2C | ADS1115 4-channel ADC |
| `mcp23017` | [GPIO](../interfaces/gpio.md) | I2C | MCP23017 16-bit I/O expander |
| `tca9548a` | [ColorSensor](../interfaces/color-sensor.md) | I2C | TCA9548A mux + TCS34725 |
| `rplidar` | [Lidar2D](../interfaces/lidar.md) | Serial (USB) | RPLidar A2 |
| `tim` | [Lidar2D](../interfaces/lidar.md) | Serial (USB) | SICK TIM laser |
| `ws2812b` | [LedStrip](../interfaces/led-strip.md) | SPI/PWM | WS2812B addressable LEDs |
| `pump` | [GPIO](../interfaces/gpio.md) | GPIO | Vacuum pump |
| `magnet` | [GPIO](../interfaces/gpio.md) | GPIO | Electromagnet |
| `proximity` | [GPIO](../interfaces/gpio.md) | GPIO | Proximity sensor |
| `recal` | [GPIO](../interfaces/gpio.md) | GPIO | Recalibration distance sensor |

## Relationship with config

Driver instances are created from JSON5 configuration files in [evo-robot-configs](https://github.com/evolutek/evo-robot-configs). The factory function in each driver module reads the relevant config section and instantiates the correct implementation.

## See also

- [Peripheral hierarchy](peripheral.md) — base classes (Peripheral, Interface, Placable, InterfaceHolder)
- [Fake](fake.md) — simulation implementations for testing
