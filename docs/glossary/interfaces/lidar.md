# Lidar2D

A **Lidar2D** is a 2D rotating laser scanner that produces distance measurements at multiple angles.

## Class: `Lidar2D`

**Module:** `evo_lib.interfaces.lidar`
**Extends:** [Placable](../architecture/peripheral.md#placable)

| Method | Returns | Description |
|--------|---------|-------------|
| `start()` | [Task](../concurrency/task.md)\[None\] | Start continuous scanning |
| `stop()` | [Task](../concurrency/task.md)\[None\] | Stop scanning |
| `iter(duration?)` | Generator\[Lidar2DMeasure\] | Iterate over individual measurements |
| `on_scan()` | [Event](../concurrency/event.md)\[list\[Lidar2DMeasure\]\] | Event that fires on each complete scan |

### Scanning modes

- **Polling:** use `iter()` to process measurements one by one in a loop
- **Event-driven:** use `on_scan()` to get a callback with each complete 360° scan batch

## Class: `Lidar2DMeasure`

**Module:** `evo_lib.interfaces.lidar`

A single distance measurement from the lidar.

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `angle` | float | radians | Angle of this measurement |
| `distance` | float | mm | Distance to the detected object |
| `timestamp` | float | seconds | Time of measurement |
| `quality` | float | 0–255 | Signal quality / confidence |

Uses `__slots__` for memory efficiency (thousands of measurements per scan).

## Drivers

| Driver | Hardware | Bus |
|--------|----------|-----|
| `rplidar` | RPLidar A2 | Serial (USB, CP210x → ttyUSB0) |
| `tim` | SICK TIM laser | Serial (USB) |

## See also

- [Peripheral hierarchy](../architecture/peripheral.md) — base classes
- [Event](../concurrency/event.md) — `on_scan()` returns an Event
