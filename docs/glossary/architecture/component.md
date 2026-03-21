# Component

A **Component** is the lifecycle base class for every hardware device in the library.

## Purpose

Every piece of hardware (sensor, actuator, servo, GPIO pin) must acquire resources on startup and release them on shutdown. `Component` enforces this contract with two abstract methods: `init()` and `close()`.

## Class: `Component`

**Module:** `evo_lib.component`

```python
class Component(ABC):
    def __init__(self, name: str): ...

    @property
    def name(self) -> str: ...

    @abstractmethod
    def init(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...
```

| Member | Description |
|--------|-------------|
| `name` | Human-readable identifier for logging and debugging (e.g. `"lidar_front"`) |
| `init()` | Acquire hardware resources (open bus, configure registers, start threads) |
| `close()` | Release hardware resources (stop threads, close handles, reset state) |

Every [Interface](interface.md) and [Driver](driver.md) inherits from `Component`.

## See also

- [ComponentHolder](component-holder.md) — a Component that owns other Components
- [Interface](interface.md) — abstract contracts that extend Component
- [Driver](driver.md) — concrete implementations
- [Fake](fake.md) — simulation implementations
