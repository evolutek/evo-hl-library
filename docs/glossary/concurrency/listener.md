# Listener

A **Listener** is a callback entry, and **Listeners** is a registry that manages a collection of them.

## Purpose

Listeners provide the base callback mechanism used by [Event](event.md). On its own,
Listeners is **not** thread-safe — it is a simple building block.

## Class: `Listener[*T]`

**Module:** `evo_lib.listeners`

A single callback entry. Holds a reference to the callback function and a flag indicating whether it should fire only once.

| Field | Description |
|-------|-------------|
| `_callback` | The callback function |
| `_onetime` | If True, automatically removed after the first trigger |

## Class: `Listeners[*T]`

**Module:** `evo_lib.listeners`

A registry of Listener entries with register, unregister, and trigger operations.

| Method | Description |
|--------|-------------|
| `register(callback, onetime=False) → Listener` | Add a callback. Returns a handle for removal |
| `unregister(listener) → None` | Remove a previously registered callback |
| `trigger(*args) → None` | Invoke all callbacks. One-time listeners are removed after invocation |

### One-time listeners

When `onetime=True`, the listener fires once on the next `trigger()` call, then is automatically removed from the registry.

## Thread safety

**Not thread-safe.** For a thread-safe version with blocking wait, use [Event](event.md),
which extends Listeners and adds `threading.Condition` synchronization.

## See also

- [Event](event.md) — thread-safe extension with blocking wait
