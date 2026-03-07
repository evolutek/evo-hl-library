# evo_hl_library

Reusable hardware drivers and utilities for Evolutek competition robots.

## What is this?

A Python library providing bus-agnostic drivers for sensors, actuators, and GPIO. Each driver comes with a simulation/fake implementation for testing without hardware.

This library has **no dependency** on cellaserv, competition rules, or robot-specific logic. It can be used on any robot project.

## Ecosystem

| Repo | Role |
|------|------|
| **evo_hl_library** (this repo) | Reusable hardware drivers and utilities |
| **evo_hl_omnissiah** | Robot brain, consumes this library |
| **evo_robot_configs** | JSON5 configuration per robot and year |
| **evo_utils** | Shared utilities (config loader, logging, LocalBus) |

## What goes here

Drivers consumed by Omnissiah's **Action** and **Trajman** briques:

| Driver | Hardware | Bus | Used by |
|--------|----------|-----|---------|
| PCA9685Driver | PWM servo controller | I2C | Action |
| AX12Driver | Dynamixel servos | Serial (USB2AX) or CAN proxy | Action |
| CANDriver | Carte asserv communication | CAN (MCP2515 SPI) | Trajman |
| TCA9548ADriver | I2C multiplexer → color sensors | I2C | Action |
| ADS1115Driver | ADC → recalibration sensors | I2C | Action |
| LidarDriver | RPLidar 2D | UART | Orchestrator |

Each driver follows the same structure:

```
evo_hl/<driver>/
├── base.py       # Abstract base class (interface)
├── rpi.py        # Real RPi implementation
├── fake.py       # Simulation implementation
└── config.py     # Pydantic model for this driver's config
```

## Boundary rule

If the code can be reused on a completely different robot (industrial arm, drone, another competition robot), it belongs here. If it is specific to Evolutek's match logic, it belongs in `evo_hl_omnissiah`.
