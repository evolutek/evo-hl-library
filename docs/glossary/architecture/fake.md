# Fake

A **Fake** is a simulation implementation of a [Driver](driver.md) that requires no physical hardware.

## Purpose

Fakes allow running and testing robot code on a development machine (laptop, CI server) without any hardware connected. They implement the same [Interface](interface.md) as real drivers but return predetermined or injected values.

## Characteristics

| Aspect | Real driver | Fake driver |
|--------|------------|-------------|
| Hardware | Required | Not needed |
| Bus access | I2C, SPI, serial, GPIO | None |
| Return values | Read from hardware | Injected or hardcoded |
| Side effects | Moves motors, toggles pins | Logs or no-ops |
| Speed | Hardware-limited | Instant |

## Typical fake patterns

- **Hardcoded values:** `read_voltage()` always returns `3.3`
- **Value injection:** test code sets `fake.next_value = 42`, then `read()` returns `42`
- **Recording:** fake records all calls for later assertion
- **No-op:** `move_to_angle(90)` does nothing, returns an immediate [Task](../concurrency/task.md)

## File location

Each driver module has a `fake.py` alongside the real implementation:

```
evo_lib/drivers/<name>/
├── rpi.py    # Real
└── fake.py   # Fake
```

The [factory](driver.md) function selects real or fake based on configuration.

## See also

- [Driver](driver.md) — the real implementation counterpart
- [Peripheral hierarchy](peripheral.md) — the contracts both real and fake implement
- [Task](../concurrency/task.md) — fakes typically return `ImmediateResultTask` for instant completion
