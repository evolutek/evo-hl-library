# Event

An **Event** is a multi-shot, thread-safe notification mechanism. Unlike [Task](task.md)
(which completes once), an Event can fire repeatedly.

## Purpose

Some hardware produces recurring signals: a GPIO interrupt fires every time a sensor
triggers, a lidar completes a new scan every 100ms. Event models these patterns.

```python
event = gpio.interrupt(GPIOEdge.RISING)
event.register(lambda state: print(f"Pin went {'high' if state else 'low'}"))
event.wait()  # blocks until next trigger
```

## Class: `Event[*T]`

**Module:** `evo_lib.event`

Extends [Listeners](listener.md) with thread-safe trigger and blocking wait.

| Method | Description |
|--------|-------------|
| `register(callback) → Listener` | Add a callback invoked on every future trigger |
| `unregister(listener) → None` | Remove a previously registered callback |
| `wait(timeout?) → bool` | Block until the next trigger. Returns False on timeout |
| `trigger(*args) → None` | Fire the event: wake all waiters and invoke all callbacks |

## Semantics

### Multi-shot

`trigger()` can be called any number of times. Each call wakes all current waiters and
invokes all registered callbacks.

### Wait is forward-looking

`wait()` always waits for the **next** trigger, not a past one. If the event was triggered
5 seconds ago, `wait()` still blocks until the next trigger.

This is implemented via a generation counter: each `trigger()` increments the counter,
and `wait()` blocks until the counter changes.

### Callbacks outside the lock

Callbacks are collected under the lock, then invoked **outside** the lock. This prevents
a slow callback from blocking other threads that need to register/unregister or wait.

## Thread safety

Fully thread-safe. Multiple threads can concurrently:
- Call `wait()` (all wake on trigger)
- Call `register()` / `unregister()`
- Call `trigger()`

Uses `threading.Condition` internally.

## See also

- [Task](task.md) — one-shot async operation (Event is multi-shot)
- [Listener](listener.md) — the non-thread-safe callback registry that Event extends
- [GPIO](gpio.md) — `interrupt()` returns an Event
- [Lidar2D](lidar.md) — `on_scan()` returns an Event
