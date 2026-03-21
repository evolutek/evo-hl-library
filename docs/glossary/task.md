# Task

A **Task** represents an asynchronous operation that may complete later, fail, or be
cancelled. It is the primary return type of [Interface](interface.md) methods.

## Purpose

Hardware operations take time (a servo moves, a sensor samples, a lidar scans). Instead
of blocking the caller, interface methods return a Task. The caller can then:

- **Wait** synchronously: `task.wait(timeout=2.0)`
- **Register callbacks**: `task.on_complete(lambda v: ...)`
- **Cancel**: `task.cancel()`

Tasks replace asyncio in this project. See [Event](event.md) for recurring notifications.

## Class hierarchy

```
Task[T]  (ABC)
├── ImmediateResultTask[T]   — result known at construction
├── ImmediateErrorTask[T]    — error known at construction
└── DelayedTask[T]           — thread-safe, completes later
```

**Module:** `evo_lib.task`

## Class: `Task[T]`

Abstract base. Defines the consumer API.

| Method | Description |
|--------|-------------|
| `wait(timeout?) → T` | Block until done. Returns value or raises exception |
| `is_done() → bool` | True if completed (success or error) |
| `on_complete(cb) → Task` | Register success callback. Chainable |
| `on_error(cb) → Task` | Register error callback. Chainable |
| `cancel() → Task` | Cancel the operation. Chainable |

## Class: `ImmediateResultTask[T]`

The result is already known when the Task is created. No thread synchronization needed.

Typical use: operations that complete instantly (e.g. reading a cached value, setting a
buffer pixel on a [LedStrip](led-strip.md)).

```python
return ImmediateResultTask(3.3)  # voltage already known
```

`wait()` returns immediately. `on_complete()` calls the callback synchronously.

## Class: `ImmediateErrorTask[T]`

Same as ImmediateResultTask but for errors known at construction time.

```python
return ImmediateErrorTask(HardwareError("bus timeout"))
```

`wait()` raises the error immediately. `on_error()` calls the callback synchronously.

## Class: `DelayedTask[T]`

Thread-safe Task for operations that complete in a background thread. This is the most
common variant for real hardware operations.

### Consumer API

Same as Task (wait, is_done, on_complete, on_error, cancel).

### Producer API

| Method | Description |
|--------|-------------|
| `complete(value) → None` | Mark as successfully completed, wake all waiters |
| `error(exception) → None` | Mark as failed, wake all waiters |

### Constructor

```python
DelayedTask(on_cancel: Callable[[], None] = None)
```

The optional `on_cancel` callback is invoked when `cancel()` is called, before the Task
is marked as cancelled. Use this to stop the underlying hardware operation (e.g. halt a
motor).

## Exceptions

### `TaskCancelledError`

Raised by `wait()` when the Task has been cancelled.

### `TaskTimeoutError`

Raised by `wait(timeout=...)` when the timeout elapses before completion.

## Thread safety

| Class | Thread-safe |
|-------|-------------|
| `ImmediateResultTask` | Yes (immutable after construction) |
| `ImmediateErrorTask` | Yes (immutable after construction) |
| `DelayedTask` | Yes (uses `threading.Lock` + `threading.Event`) |

## See also

- [Event](event.md) — multi-shot notifications (Task is one-shot)
- [Interface](interface.md) — all interface methods return Task or Event
- [Listener](listener.md) — callback mechanism used internally
