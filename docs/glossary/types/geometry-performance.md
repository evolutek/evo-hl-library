# Geometry Performance Notes

Evolutek robots run on constrained hardware: Raspberry Pi for the main compute, STM32 (Cortex-M) for the slave boards. Trigonometry and heap allocations in hot paths cost real latency.

This page lists the tricks used inside the geometry module and the patterns to follow (or avoid) in user code.

---

## Trigonometric cost, order of magnitude

| Platform | Clock | `sinf` / `cosf` | `atan2f` | `sqrtf` | ~ wall time for `sinf` |
|----------|-------|-----------------|----------|---------|------------------------|
| Raspberry Pi 4 (Cortex-A72, hard FPU + NEON) | 1.5 GHz | ~30-50 cy | ~80-120 cy | 1-5 cy (FSQRT) | ~25 ns |
| STM32G4 (Cortex-M4F, hard single-precision FPU) | 170 MHz | ~30-80 cy | ~150-250 cy | ~14 cy (VSQRT) | ~300 ns |
| ESP32 (Xtensa LX6, single-precision FPU) | 240 MHz | ~100-200 cy | ~300-400 cy | ~10-20 cy | ~600 ns |
| Cortex-M0/M3 (no FPU, soft-float) | ~48-72 MHz | ~200-400 cy | ~500 cy | ~100-200 cy | ~5 µs |
| PC x86_64 (modern desktop) | ~4 GHz | ~15-30 cy | ~40 cy | 1 cy | ~5 ns |

Orders of magnitude, not benchmarks: exact figures depend on libm version, compiler flags, and `float` vs `double`. Takeaway: on the RPi a `sinf` costs a few tens of nanoseconds; on an STM32G4 it costs a few hundred; without a FPU, it crosses the microsecond.

At a 1 kHz control loop, those cycles matter. A `Pose2D.transform(point)` call with on-the-fly `cos`/`sin` costs roughly 50–80 cycles on RPi. Multiply by a 360-point lidar scan at 10 Hz = 3600 trig pairs per second just for frame conversion.

The STM32G4 is the target for most Evolutek slave boards (asserv, actionneurs, alim…): it has a single-precision FPU, so `sinf`/`cosf` are fast in absolute terms, but the 170 MHz clock and in-order pipeline make per-call overhead visible in tight control loops. Caching `cos`/`sin` (as `RigidTransform2D` does) remains worthwhile.

---

## Three levels of optimization

1. **Algorithmic** — pick a different formula that avoids the expensive call entirely.
2. **Representational** — store something else than an angle (unit vector, quaternion) so the expensive conversion is paid once, at object creation.
3. **Hardware** — when you can't avoid it: polynomial approximations, lookup tables, fused instructions.

Exhaust level 1 before moving to level 2, and level 2 before level 3.

---

## Pattern 1 — Compare squared distances, not distances

Computing `sqrt` is pointless when you only want to order distances or test them against a threshold.

```python
# Bad: sqrt for nothing
if (robot.position - target).norm() < 50:
    ...

# Good: square the threshold once
RADIUS_SQ = 50 * 50
if (robot.position - target).sqr_norm() < RADIUS_SQ:
    ...
```

`Vect2D.sqr_norm()` and `Vect3D.sqr_norm()` exist precisely for this. Prefer them whenever possible.

---

## Pattern 2 — Compare angles via dot product

To test whether two headings are close (say, within 5°), you do **not** need `atan2` or `normalize_angle`.

Store the orientation as a unit vector `(cos θ, sin θ)` and compare dot products to a precomputed cosine threshold:

```python
import math

COS_5_DEG = math.cos(math.radians(5))    # precomputed once

def heading_close(v1: Vect2D, v2: Vect2D) -> bool:
    """True if the angle between v1 and v2 is less than 5 degrees."""
    return v1.x * v2.x + v1.y * v2.y > COS_5_DEG
```

**Cost**: 2 mul + 1 add + 1 compare. No trig at all.

Versus the naive version — `abs(normalize_angle(theta1 - theta2)) < tol` — which triggers `atan2` inside `normalize_angle`.

This is the same idea that makes quaternions attractive in 3D: **never convert back to an angle in the hot path**.

---

## Pattern 3 — Cache `cos` / `sin` for a transformation

`Pose2D.transform(point)` computes `cos(theta)` and `sin(theta)` every call. Fine for one-shot usage; terrible in a loop.

When you need to apply the **same** transformation to many points, use `RigidTransform2D`: it caches `_c`, `_s` once in `__init__` and reuses them on every `apply_to_point`.

```python
# Bad: N trig pairs for N points
for p in point_cloud:
    q = robot_pose.transform(p)      # 2 trig calls per point
    results.append(q)

# Good: 1 trig pair, reused N times
T = RigidTransform2D(
    offset=Vect2D(robot_pose.x, robot_pose.y),
    angle=robot_pose.theta,
)
for p in point_cloud:
    T.apply_to_point(p)              # 4 mul + 4 add, zero trig
```

If you implement a new rotation-heavy routine, expose a version that accepts a precomputed `(c, s)` pair or a `RigidTransform2D`.

---

## Pattern 4 — Average angles without trigonometry

Given `N` angle measurements that are **close to each other** (the usual case for filtering sensor noise), avoid the full Cartesian mean.

### Fastest: wrap around a reference, then arithmetic mean

```python
TWO_PI = 2 * math.pi

def mean_angles(angles):
    """Circular mean, no trig. Valid when all angles lie in the same half-circle."""
    ref = angles[0]
    total = 0.0
    for a in angles:
        d = a - ref
        if d > math.pi:     d -= TWO_PI
        elif d < -math.pi:  d += TWO_PI
        total += d
    return ref + total / len(angles)
```

**Cost**: `N` subtractions + up to `N` compares + 1 division. Zero trig.

### Slower but robust: Cartesian mean

```python
def mean_angles_robust(angles):
    """Works for any distribution, including angles scattered around the circle."""
    x = sum(math.cos(a) for a in angles) / len(angles)
    y = sum(math.sin(a) for a in angles) / len(angles)
    return math.atan2(y, x)
```

**Cost**: `2N` trig calls + `atan2`. Pay this only if you actually cannot bound the measurements to a half-circle.

---

## Pattern 5 — Normalize angles by subtraction, not `atan2`

`atan2(sin(x), cos(x))` is a common idiom to wrap an angle into `(-π, π]`, but it uses trig. When you know the input is "a small number of turns off", subtract `2π` directly.

```python
TWO_PI = 2 * math.pi

def normalize_angle(a: float) -> float:
    while a > math.pi:  a -= TWO_PI
    while a < -math.pi: a += TWO_PI
    return a
```

**Cost**: 0-2 subtractions in practice, since inputs rarely drift beyond one or two turns. If your pipeline generates wildly drifting angles, use a modulo-based normalization (`a - TWO_PI * floor((a + pi) / TWO_PI)`) instead of the loop.

---

## Pattern 6 — Avoid allocations in the hot loop

Python does not free memory synchronously; creating `Vect2D` instances inside a 10 kHz loop pressures the allocator and can trigger GC pauses on RPi.

Prefer in-place operators (`+=`, `-=`, `*=`, `_components` setter) on a reused buffer:

```python
# Bad: allocates one Vect2D per iteration
acc = Vect2D(0, 0)
for p in points:
    acc = acc + p

# Good: mutates the accumulator, zero new objects
acc = Vect2D(0, 0)
for p in points:
    acc += p
```

Same idea for `RigidTransform2D.apply_to_point` — it mutates the argument in place rather than returning a new `Vect2D`.

---

## Pattern 7 — Polynomial approximations (when on bare MCU)

On a Cortex-M without FPU, even `sinf` hurts. Two cheap substitutes, from cheapest to most accurate:

```c
// Taylor-truncated, good for |x| < 0.5 rad, error ~0.5%
static inline float sin_small(float x) { return x - (x * x * x) / 6.0f; }
static inline float cos_small(float x) { return 1.0f - (x * x) / 2.0f; }

// Bhaskara I approximation, good over [-π, π], error ~1.6%
static inline float sin_bhaskara(float x) {
    // normalize x to [0, π] first
    return (16.0f * x * (3.14159265f - x)) /
           (5.0f * 3.14159265f * 3.14159265f - 4.0f * x * (3.14159265f - x));
}
```

**Cost**: 3-5 multiplications. Usually beats `sinf` on soft-float targets.

Not applicable to Python code, but useful to know for firmware that implements the same geometry on the STM32 boards.

---

## Pattern 8 — Lookup tables

For **discrete** angle inputs (e.g. encoder ticks, 4096 steps per revolution):

```c
static const float SIN_LUT[4096] = { /* precomputed at build time */ };

float sin_lut(uint16_t tick) { return SIN_LUT[tick & 0x0FFF]; }
```

**Cost**: 1 load. Constant time.

Relevant for motor control (FOC), less useful for high-level 2D robotics where angles are floats.

---

## Decision tree: what to use when

| Situation | Pattern |
|-----------|---------|
| Compare distances | Pattern 1 (`sqr_norm`) |
| Compare two headings | Pattern 2 (dot product of unit vectors) |
| Rotate many points by the same angle | Pattern 3 (`RigidTransform2D` with cached `_c`, `_s`) |
| Average noisy heading measurements | Pattern 4, "fastest" version |
| Average angles scattered over the whole circle | Pattern 4, "robust" version |
| Normalize a slightly drifting angle | Pattern 5 (subtraction loop) |
| Accumulate in a loop | Pattern 6 (in-place operators) |
| Bare MCU, no FPU | Pattern 7 (polynomial approx) |
| Discrete encoder angle | Pattern 8 (LUT) |

---

## Notes on the current implementation

- `RigidTransform2D.__init__` caches `_c`, `_s` — good.
- `Pose2D.transform` calls `point.rotate(theta)`, which computes `cos`/`sin` every time — **acceptable for one-shot work**, avoid in tight loops (switch to `RigidTransform2D`).
- `Vect2D.sqr_norm` exists: use it.
- Euler-to-quaternion conversion in `Pose3D.__init__` pays the trig cost **once** at construction. All subsequent `transform`/`compose` calls are pure multiply-add. This is intentional.
- `Pose3D.from_quaternion` bypasses `_euler_to_quat` entirely — use it when you already have a unit quaternion (e.g. IMU output).

---

## Takeaway

1. Pay the trig cost **once**, at object creation, not every call.
2. Compare **squared** quantities whenever you only need ordering.
3. Compare **dot products**, not angles.
4. Mutate in place in hot loops.
5. Only reach for polynomial approximations or LUTs when the profiler says so.
