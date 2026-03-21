# Proposal: Locatable Components, Config-Only Pose

## Context

Some components need a physical position and orientation on the robot for their data to be usable. For example, a LiDAR's scan measurements must be transformed from sensor frame to robot frame, and a recal sensor's position determines how to compute the robot's absolute position.

This is not an intrinsic property of a component type. Any component **can** have a pose if the config declares one. A GPIO used as a recal sensor needs a pose, the same GPIO used as a pump switch does not. It's opt-in, activated per instance in the config.

## Decision

The pose is **configuration data**, not driver behavior. It lives in the config files and is consumed by omnissiah, not by the driver.

A class hierarchy (`LocatableComponent`, mixin, or optional field on `Component`) was considered but the distinction is contextual, not intrinsic: the same driver can be used with or without a pose. See [Alternatives considered](#alternatives-considered).

### Config format

> The config file structure is not finalized yet. The examples below illustrate the principle, not the exact format.

The optional `pose` field can appear **anywhere a component is declared**, following the existing config layering:

- **`platforms/<robot>.json5`**, for components fixed to the chassis. These don't change between years.
- **`<year>/robots/<robot>/assemblies.json5`**, for components attached to year-specific mechanical sub-assemblies.

```json5
// platforms/hololutek.json5, chassis-fixed components
{
  "sensors": {
    "lidar": {
      "driver": "rplidar",
      "port": "/dev/ttyUSB0",
      "pose": { "x": 0, "y": 85, "z": 200, "theta": 0 }  // mm, radians, z optional (default 0)
    },
    "recal_front_left": {
      "driver": "proximity",
      "pin": 5,
      "pose": { "x": -100, "y": 150, "theta": 1.5708 }
    }
  }
}

// 2026/robots/hololutek/assemblies.json5, year-specific
{
  "fingers": {
    "each": {
      "color_sensor": {
        "driver": "tcs34725"
        // no pose needed
      }
    }
  },
  "pump_left": {
    "driver": "pump",
    "board": "actionneurs",
    "pin": 12
    // no pose needed
  }
}
```

### Omnissiah side

At boot, the Orchestrator builds a mapping from component name to pose:

```python
# Pseudo-code
poses: dict[str, Vect2DOriented] = {}
for name, cfg in all_component_configs.items():  # merged from platform + assemblies
    if "pose" in cfg:
        poses[name] = Vect2DOriented.from_dict(cfg["pose"])
```

Briques that need poses (Trajman for lidar transforms, Action for recal computation) receive the relevant poses at construction.

## Alternatives considered

| Option | Reason rejected |
|--------|-----------------|
| `LocatableComponent(Component)` subclass | Would split the class hierarchy for a contextual distinction |
| Optional `pose` field on `Component` | Pollutes all components, mixes config with behavior |
| Pose as a mixin | Forces the decision at interface level |
