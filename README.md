# evo_hl_library

Reusable hardware drivers and utilities for Evolutek competition robots.

## What is this?

A Python library providing bus-agnostic drivers for sensors, actuators, and GPIO.
Each driver comes with a simulation/fake implementation for testing without hardware.

This library has **no dependency** on cellaserv, competition rules, or robot-specific logic.
It can be used on any robot project.

## Ecosystem

| Repo | Role |
|------|------|
| **evo_hl_library** (this repo) | Reusable hardware drivers and utilities |
| **evo_hl_omnissiah** | Robot brain, consumes this library |
| **evo_robot_configs** | YAML configuration per robot and year |
