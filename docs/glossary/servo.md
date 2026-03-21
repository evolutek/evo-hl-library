# Servo

A **Servo** is an angle-controlled actuator driven by PWM. A **SmartServo** extends Servo
with position feedback and speed control.

## Class: `Servo`

**Module:** `evo_lib.interfaces.servo`
**Extends:** [Component](component.md)
**Locatable:** No

| Method | Returns | Description |
|--------|---------|-------------|
| `move_to_angle(angle)` | [Task](task.md)\[None\] | Move to the given angle in degrees |
| `move_to_fraction(fraction)` | [Task](task.md)\[None\] | Set position as 0.0–1.0 fraction of full range |
| `free()` | [Task](task.md)\[None\] | Disable PWM output (servo goes limp) |

A basic Servo is fire-and-forget: you command a position but have no feedback on whether
it reached it.

### Driver

| Driver | Hardware | Bus |
|--------|----------|-----|
| `pca9685` | PCA9685 16-channel PWM controller | I2C (addr 0x40) |

## Class: `SmartServo` {#smartservo}

**Module:** `evo_lib.interfaces.smart_servo`
**Extends:** Servo
**Locatable:** No

A SmartServo can report its actual position, has configurable speed, and communicates
over a bidirectional bus.

| Method | Returns | Description |
|--------|---------|-------------|
| `move_to_position(position)` | [Task](task.md)\[None\] | Move to position in native units |
| `get_position()` | [Task](task.md)\[int\] | Read current position (native units) |
| `get_angle()` | [Task](task.md)\[float\] | Read current position (degrees) |
| `get_fraction()` | [Task](task.md)\[float\] | Read current position (0.0–1.0) |
| `set_speed(speed)` | [Task](task.md)\[None\] | Set movement speed (0.0–1.0 fraction) |

Plus all methods from Servo (`move_to_angle`, `move_to_fraction`, `free`).

### Driver

| Driver | Hardware | Bus |
|--------|----------|-----|
| `ax12` | Dynamixel AX-12A | Serial via USB2AX |

## Servo vs SmartServo

| Feature | Servo | SmartServo |
|---------|-------|------------|
| Position command | Yes | Yes |
| Position feedback | No | Yes |
| Speed control | No | Yes |
| Communication | One-way (PWM) | Bidirectional (serial) |
| Typical hardware | PCA9685 | Dynamixel AX-12 |

## See also

- [Component](component.md) — lifecycle base class
- [Pilot](pilot.md) — higher-level movement abstraction that may use servos internally
