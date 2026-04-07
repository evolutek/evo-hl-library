# Pilot

A **Pilot** is the movement controller for the robot. It abstracts away the drive type (differential or holonomic) and communicates with the motion control board (carte asserv).

## Class hierarchy

```
Pilot  (Placable)
├── DifferentialPilot   — two-wheel drive (left/right)
└── HolonomicPilot      — omnidirectional (extends DifferentialPilot)
```

**Module:** `evo_lib.interfaces.pilot`

## Class: `Pilot`

Base class with emergency controls.

| Method | Returns | Description |
|--------|---------|-------------|
| `stop()` | [Task](../concurrency/task.md)\[None\] | Immediately stop current movement (motors brake) |
| `free()` | [Task](../concurrency/task.md)\[None\] | Stop motors and go into freewheel (no braking) |

## Class: `DifferentialPilot`

For robots with two driven wheels (left/right). The robot can move forward and rotate in place, but cannot strafe sideways.

| Method | Returns | Description |
|--------|---------|-------------|
| `go_to(x, y)` | Task\[PilotMoveStatus\] | Move to position |
| `go_to_then_head_to(x, y, heading)` | Task\[PilotMoveStatus\] | Move, then rotate to heading |
| `go_to_then_rotate(x, y, angle)` | Task\[PilotMoveStatus\] | Move, then rotate by angle |
| `go_to_then_look_at(x, y, lx, ly)` | Task\[PilotMoveStatus\] | Move, then face a point |
| `forward(distance)` | Task\[PilotMoveStatus\] | Move forward by distance |
| `head_to(heading)` | Task\[PilotMoveStatus\] | Rotate to absolute heading |
| `look_at(x, y)` | Task\[PilotMoveStatus\] | Rotate to face a point |
| `rotate(angle)` | Task\[PilotMoveStatus\] | Rotate by relative angle |
| `follow_path(waypoints)` | Task\[PilotMoveStatus\] | Follow a sequence of waypoints |

### "then" vs "while"

`go_to_then_rotate`: move first, **then** rotate (sequential — differential can't do both).
`go_to_while_rotate`: move **and** rotate simultaneously (holonomic only).

## Class: `HolonomicPilot`

Extends DifferentialPilot with simultaneous translation + rotation.

| Method | Returns | Description |
|--------|---------|-------------|
| `go_to_while_head_to(x, y, heading)` | Task\[PilotMoveStatus\] | Move and rotate to heading simultaneously |
| `go_to_while_rotate(x, y, angle)` | Task\[PilotMoveStatus\] | Move and rotate by angle simultaneously |
| `go_to_while_look_at(x, y, lx, ly)` | Task\[PilotMoveStatus\] | Move while facing a point |
| `follow_holonomic_path(waypoints)` | Task\[PilotMoveStatus\] | Follow waypoints with independent heading |

Plus all methods from DifferentialPilot.

## Enum: `PilotMoveStatus`

Result of a movement command.

| Value | Meaning |
|-------|---------|
| `ERROR` | Movement failed (hardware error) |
| `MOVING` | Still in progress |
| `REACHED` | Destination reached successfully |
| `BLOCKED` | Obstacle detected, movement aborted |
| `CANCELLED` | Movement was cancelled by the caller |

## Dataclass: `DifferentialPilotWaypoint`

A point on a path for a differential robot.

| Field | Type | Description |
|-------|------|-------------|
| `x` | float | X coordinate |
| `y` | float | Y coordinate |
| `heading` | float | Orientation in radians at this waypoint |
| `velocity` | float | Speed at this waypoint (positive) |

## Dataclass: `HolonomicPilotWaypoint`

Extends DifferentialPilotWaypoint with a tangent field.

| Field | Type | Description |
|-------|------|-------------|
| `tangent` | float | Direction of velocity vector in radians (independent from heading) |

Plus all fields from DifferentialPilotWaypoint.

## See also

- [Peripheral hierarchy](../architecture/peripheral.md) — base classes
- [Task](../concurrency/task.md) — all movement methods return Task\[PilotMoveStatus\]
