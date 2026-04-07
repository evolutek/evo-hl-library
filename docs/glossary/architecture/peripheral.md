# Peripheral hierarchy

All hardware abstractions inherit from `Peripheral`, the lifecycle base class.

**Module:** `evo_lib.peripheral`

## Class tree

```
Peripheral (ABC)
├── Interface          # Bus or I/O protocol (I2C, Serial, GPIO)
├── Placable           # Device with a physical position (Servo, Lidar, Pilot, ...)
└── InterfaceHolder    # Multi-channel chip that owns child Peripherals
```

## Peripheral

Lifecycle contract: every hardware object must implement `init()` and `close()`.

```python
class Peripheral(ABC):
    def __init__(self, name: str): ...
    def name(self) -> str: ...         # property
    def init(self) -> None: ...        # abstract
    def close(self) -> None: ...       # abstract
```

## Interface

Base class for transport/protocol peripherals. Drivers receive an Interface at construction instead of creating their own bus connection.

```python
class Interface(Peripheral): ...
```

| Subclass | Module | Role |
|----------|--------|------|
| I2C | `evo_lib.interfaces.i2c` | I2C bus (read/write/scan) |
| Serial | `evo_lib.interfaces.serial` | UART (read/write/flush) |
| GPIO | `evo_lib.interfaces.gpio` | Digital I/O pin (read/write/interrupt) |

## Placable

Base class for devices that robot logic interacts with directly. The name reflects that they can have a physical pose in config.

```python
class Placable(Peripheral): ...
```

| Subclass | Module | Role |
|----------|--------|------|
| Servo | `evo_lib.interfaces.servo` | Angle-controlled PWM servo |
| SmartServo | `evo_lib.interfaces.smart_servo` | Servo with position feedback (AX-12) |
| Pilot | `evo_lib.interfaces.pilot` | Robot movement controller |
| AnalogInput | `evo_lib.interfaces.analog_input` | Analog voltage input |
| ColorSensor | `evo_lib.interfaces.color_sensor` | RGB color sensor |
| Lidar2D | `evo_lib.interfaces.lidar` | 2D scanning lidar |
| LedStrip | `evo_lib.interfaces.led_strip` | Addressable LED strip |

Placable methods return [Task](../concurrency/task.md) or [Event](../concurrency/event.md), never raw values.

## InterfaceHolder

A Peripheral that owns child Peripherals. Used for multi-channel chips.

```python
class InterfaceHolder(Peripheral):
    def get_subcomponents(self) -> list[Peripheral]: ...  # abstract
```

| Holder | Children |
|--------|----------|
| MCP23017 | 16 GPIO pins |
| TCA9548A | up to 8 ColorSensors |
| ADS1115 | 4 AnalogInputs |
| PCA9685 | 16 Servos |

The holder initializes the bus first, then its children. On close, children are closed before the bus.

## How they connect

```
                  ┌────────────────────────┐
                  │     InterfaceHolder     │
                  │  (MCP23017, TCA9548A)   │
                  │                         │
                  │  owns ──► child Placable │
                  │  uses ──► Interface      │
                  └────────────────────────┘

       Interface ◄──── injected into ────► Driver (implements Placable)
    (I2C, Serial)                         (PCA9685Servo, AX12SmartServo)
```

A [Driver](driver.md) is the concrete class that implements a Placable (or Interface) contract. Each driver has a real implementation (`rpi.py`) and a [Fake](fake.md) (`virtual.py`).

## See also

- [Driver](driver.md) — concrete implementations
- [Fake](fake.md) — simulation implementations
- [Locatable Components](../types/locatable-components.md) — config-driven pose for Placable devices
