# Component

A **Component** is the lifecycle base class for every hardware device in the library.

## Purpose

Every piece of hardware (sensor, actuator, servo, GPIO pin) must acquire resources on
startup and release them on shutdown. `Component` enforces this contract with two abstract
methods: `init()` and `close()`.

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

## Class: `ComponentHolder`

A **ComponentHolder** is a Component that manages other Components. It adds a single
method to expose its children.

```python
class ComponentHolder(Component):
    @abstractmethod
    def get_subcomponents(self) -> list[Component]: ...
```

### When to use ComponentHolder

Use `ComponentHolder` when a single logical device is composed of multiple sub-devices.
For example, a TCA9548A I2C multiplexer owns several ColorSensor channels — the mux is
the holder, each channel is a child Component.

The holder is responsible for calling `init()` / `close()` on its children in the right
order.

## Locatable vs non-locatable

Some components have a meaningful **physical position and orientation** on the robot:

- A **LiDAR** mounted at the front, angled at 15° — its measurements depend on its pose
- A **ColorSensor** pointing downward under a gripper finger

Others are position-independent:

- A **GPIO pin** — its function is purely electrical
- A **Servo** channel on a PCA9685 — the channel number matters, not where the board sits

This distinction is documented in each [Interface](interface.md) but is not enforced at
the class level. Locatable components typically receive their pose from the robot
[configuration](https://github.com/evolutek/evo-robot-configs).

## See also

- [Interface](interface.md) — abstract contracts that extend Component
- [Driver](driver.md) — concrete implementations
- [Fake](fake.md) — simulation implementations
