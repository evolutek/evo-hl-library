# Geometry Examples

Worked examples for the `Vect2D` / `Pose2D` / `Pose3D` / `RigidTransform2D` types.

The goal is to build correct intuition: when do you use `+`, when do you use `compose`, when does the naive formula produce silently wrong results.

---

## 1. ℝ² vs SE(2) — the robot that moves forward

Robot at position `(100, 0)`, facing north (`θ = π/2`). It wants to move forward 50 mm **in its own direction**.

### Wrong (treating the pose as a vector)

```python
robot = Pose2D(100, 0, math.pi / 2)
delta = Pose2D(50, 0, 0)          # "go forward 50 mm"
new = robot + delta                # Pose2D(150, 0, π/2)
```

The robot teleported 50 mm **east**, not north. Adding vectors ignores the robot's orientation.

### Right (SE(2) composition)

```python
robot = Pose2D(100, 0, math.pi / 2)
delta = Pose2D(50, 0, 0)           # 50 mm forward, in the local frame
new = robot.compose(delta)         # Pose2D(100, 50, π/2)
```

`compose` applies the robot's rotation to the local offset. The robot moves 50 mm north in its own frame.

**Takeaway**: a pose's orientation decides how a local offset maps back to the parent frame. Always compose — never add.

---

## 2. Averaging angles — SO(2) is not ℝ

Two heading measurements: 359° and 1°. The true mean is 0° (or 360°, same thing).

### Naive arithmetic mean (wrong)

```python
(359 + 1) / 2 = 180     # robot would face south
```

### Through Cartesian coordinates (right)

```python
import math
angles = [math.radians(359), math.radians(1)]
x = sum(math.cos(a) for a in angles) / len(angles)
y = sum(math.sin(a) for a in angles) / len(angles)
mean = math.atan2(y, x)  # ≈ 0 radians
```

### Cheaper on embedded hardware (also right)

```python
TWO_PI = 2 * math.pi

def normalize_near(a: float, ref: float) -> float:
    """Bring *a* into [ref - π, ref + π] without trigonometry."""
    d = a - ref
    while d > math.pi:  d -= TWO_PI
    while d < -math.pi: d += TWO_PI
    return ref + d

def mean_angles(angles):
    ref = angles[0]
    return sum(normalize_near(a, ref) for a in angles) / len(angles)
```

**Why this works**: angles live on a **circle**. `359°` and `1°` are 2° apart, not 358° apart. Arithmetic averaging assumes a line, which is why it breaks around the 0/2π boundary.

See [`geometry-performance.md`](geometry-performance.md) for more options (dot-product comparisons, polynomial approximations, LUTs).

---

## 3. Sensor fusion — chaining frames

Lidar mounted at `(0, 85, 0)` on the robot (85 mm in front, same orientation as the robot). Robot at `(500, 300, π/4)` on the table.

The lidar detects an obstacle at `(200, 0)` **in its own frame**.

**Question**: where is the obstacle on the table?

```python
robot = Pose2D(500, 300, math.pi / 4)     # robot frame inside table frame
lidar_on_robot = Pose2D(0, 85, 0)          # lidar frame inside robot frame

# Lidar frame inside table frame (SE(2) composition)
lidar_on_table = robot.compose(lidar_on_robot)
# ≈ Pose2D(500 - 85·sin(π/4), 300 + 85·cos(π/4), π/4)
# ≈ Pose2D(439.9, 360.1, π/4)

# Obstacle in the lidar frame
obstacle_local = Vect2D(200, 0)

# Obstacle on the table
obstacle_global = lidar_on_table.transform(obstacle_local)
# ≈ Vect2D(439.9 + 200·cos(π/4), 360.1 + 200·sin(π/4))
# ≈ Vect2D(581.3, 501.5)
```

Two different operations on two different types:

| Operation | Signature | Meaning |
|-----------|-----------|---------|
| `compose` | `SE(2) × SE(2) → SE(2)` | chain two frames |
| `transform` | `SE(2) × ℝ² → ℝ²` | apply a transformation to a point |

This is exactly why `Pose` and `Vect` are distinct types.

---

## 4. Interpolating between two poses

Robot starts at `(0, 0, 0)` and must reach `(100, 0, π/2)`. Midpoint?

### Naive vector midpoint (sometimes wrong)

```python
A = Pose2D(0, 0, 0)
B = Pose2D(100, 0, math.pi / 2)
mid_wrong = Pose2D((A.x + B.x) / 2, (A.y + B.y) / 2, (A.theta + B.theta) / 2)
```

Here it gives `Pose2D(50, 0, π/4)` — correct by luck. But if `B = (100, 0, 2π - 0.1)` (almost a full turn backward), the arithmetic mean yields `π - 0.05` (half a turn the wrong way) instead of `-0.05` (just a hair backward).

### Correct (SE(2) interpolation)

```python
def shortest_angle_diff(a: float, b: float) -> float:
    return math.atan2(math.sin(b - a), math.cos(b - a))

def slerp_pose2d(A: Pose2D, B: Pose2D, t: float) -> Pose2D:
    x = A.x + t * (B.x - A.x)
    y = A.y + t * (B.y - A.y)
    theta = A.theta + t * shortest_angle_diff(A.theta, B.theta)
    return Pose2D(x, y, theta)
```

**Takeaway**: interpolation on the angle must go the **short way around the circle**, not the arithmetic way.

---

## 5. Force vs displacement vs position

Three 2D vectors, structurally identical (two floats), physically very different:

```python
F  = Vect2D(5.0, 0.0)       # force, in newtons
dx = Vect2D(50.0, 0.0)      # displacement, in millimeters
p  = Vect2D(500.0, 300.0)   # position on the table, in millimeters

# Meaningful
p_new    = p + dx            # position + displacement → new position. OK.
F_total  = F + F             # sum of forces → force. OK.
dx_scale = 2 * dx            # 2 × displacement → displacement. OK.

# Not meaningful, but Python accepts it
mix = p + F                  # "500 mm + 5 N" — dimensional nonsense
```

Python does not check units. `Vect2D` lumps three physical semantics into one type. That is a pragmatic compromise (ten classes would be too many). But putting `Pose2D` in the same bucket goes one step too far: a pose is not even a vector.

---

## 6. Inverse — going back

Robot seen from the beacon camera: `Pose2D(300, 200, π/3)`. What is the beacon, seen from the robot?

```python
robot_from_beacon = Pose2D(300, 200, math.pi / 3)
beacon_from_robot = robot_from_beacon.inverse()

# Sanity check
robot_from_beacon.compose(beacon_from_robot) == Pose2D(0, 0, 0)  # True (up to epsilon)
```

**Careful**: `inverse()` on SE(2) is **not** just negating the coordinates. The translation must also be rotated by the inverse rotation. That is exactly what `Pose2D.inverse()` does:

```python
p = Vect2D(-self.x, -self.y).rotate(-self.theta)
return Pose2D(p.x, p.y, -self.theta)
```

Writing `Pose2D(-300, -200, -π/3)` would give a completely different (and wrong) frame.

---

## 7. Composing transformations vs composing poses

`RigidTransform2D` and `Pose2D` represent the same mathematical object (an element of SE(2)), but the APIs differ:

| `Pose2D` | `RigidTransform2D` |
|----------|-------------------|
| Immutable (each operation returns a new pose) | Mutable (operations update in place) |
| Recomputes `cos`/`sin` on every `transform` | Caches `_c`, `_s` once in `__init__` |
| Convenient for one-shot computations | Efficient for repeated applications |

Use `RigidTransform2D` when you apply the **same** transformation to many points in a tight loop (lidar scan conversion, point cloud batch transform). Use `Pose2D` for everything else.

```python
# Lidar scan conversion — keep cos/sin cached
lidar_pose = robot.compose(lidar_on_robot)
T = RigidTransform2D(
    offset=Vect2D(lidar_pose.x, lidar_pose.y),
    angle=lidar_pose.theta,
)
for point in scan_points:
    T.apply_to_point(point)   # mutates in place, no allocation, no trig calls
```

---

## 8. Common pitfalls to watch for

| Anti-pattern | What to do instead |
|--------------|-------------------|
| `pose_a + pose_b` | `pose_a.compose(pose_b)` |
| `-pose` to "reverse" a pose | `pose.inverse()` |
| `(angle_a + angle_b) / 2` | `mean_angles(...)` with shortest-path reduction |
| `pose.norm()` | Meaningless (mixed units). Use `pose.position.norm()` if you need the distance from origin. |
| `2 * pose` | Meaningless. Use interpolation or composition. |
| `abs(theta_1 - theta_2) < tol` | `abs(shortest_angle_diff(theta_1, theta_2)) < tol` |
| Calling `point.rotate(theta)` inside a tight loop | Cache `(c, s)` or use `RigidTransform2D`. |
