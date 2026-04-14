# Geometry Vocabulary

Reference glossary for the mathematical and robotics terminology used by the geometry types (`Vect2D`, `Vect3D`, `Pose2D`, `Pose3D`, `RigidTransform2D`...).

Not a math course: each entry is a short definition with a pointer to where the concept shows up in the codebase.

---

## Mathematical structures

### Set
A collection of objects. No operations are assumed; you can only ask "does `x` belong to this set?".

### Group
A set with **one** operation (noted `·` or `+`) that satisfies:
1. **Closure**: `a · b` stays in the set.
2. **Associativity**: `(a · b) · c = a · (b · c)`.
3. **Identity element**: there exists `e` such that `a · e = e · a = a`.
4. **Inverse**: for every `a`, there exists `a⁻¹` such that `a · a⁻¹ = e`.

Examples: `(ℤ, +)`, `(ℝ*, ×)`, `SE(2)` under pose composition.

### Vector space (over ℝ)
A group under addition, plus a scalar multiplication `α·v` that distributes.
You can **add** vectors and **scale** them. `ℝ²`, `ℝ³` are the canonical examples.

### Manifold
A space that **locally looks like `ℝⁿ`** but may be globally curved. A circle is a 1D manifold: zoom in far enough, it looks like a line; globally, it is a closed loop.

### Lie group
A group that is also a smooth manifold: trajectories inside the group are smooth, derivatives make sense. `SO(n)`, `SE(n)`, the circle, the sphere.

### ℝ (read "R")
The set of real numbers. Infinite line.

### ℝⁿ
The set of ordered n-tuples of reals. `ℝ² = {(x, y)}`, `ℝ³ = {(x, y, z)}`.

---

## Classical groups

| Group | Name | Content |
|-------|------|---------|
| **GL(n)** | General Linear | Invertible `n × n` matrices. Biggest bucket. |
| **O(n)** | Orthogonal | Matrices that preserve distances. Rotations **and** mirrors. |
| **SO(n)** | Special Orthogonal | Pure rotations (det = +1, no mirror). `SO(2)` = circle, `SO(3)` = 3D rotations. |
| **E(n)** | Euclidean | Rotations + mirrors + translations in `ℝⁿ`. |
| **SE(n)** | Special Euclidean | Rotations + translations, **no mirror**. The group of "rigid displacements". |

In this library, `Pose2D` ∈ SE(2) and `Pose3D` ∈ SE(3).

---

## Geometric objects

### Point
A location in space. Element of `ℝⁿ` expressed in some frame. **No addition between points** (it would mean nothing physically).

### Vector
A displacement, direction, or force. Element of a vector space. Can be added, scaled, normed.

### Pose (frame)
A position **plus** an orientation. Element of `SE(n)`. Represents a local coordinate frame relative to a parent.

### Transformation
A function that moves points. In `SE(n)`, a transformation is equivalent to a pose: the pose `T` **is** the transformation that maps the parent frame onto the frame `T` defines.

### Frame (coordinate frame)
A coordinate system: "table frame", "robot frame", "lidar frame". Each pose defines a frame relative to a parent.

---

## Operations

### Translation
Pure displacement, no rotation. A vector `(tx, ty)`.

### Rotation
Change of orientation around a point (2D) or an axis (3D). Parametrized by one angle `θ` in 2D, by three angles or a quaternion in 3D.

### Rigid transformation
Rotation + translation. Preserves distances and angles. Element of `SE(n)`.

### Composition
Chaining two transformations. Noted `T₁ · T₂` or `T₁.compose(T₂)`. **Not commutative**: `T₁·T₂ ≠ T₂·T₁` in general.

### Inverse
The transformation that undoes another. `T · T⁻¹ = identity`. For a pose: "how do I step into the child frame from the parent?".

### Action
Applying a transformation to a point: `T · p` gives a new point. Distinct from `T · T'` which gives a new transformation.

---

## Orientation parameterizations

### Angle (`θ`, `theta`)
Single real number in radians. 2D only. Simple but lives on a circle (`SO(2)`), so averaging and interpolating are non-trivial.

### Heading, course, yaw
Synonyms of `θ` in 2D. In 3D, `yaw` is rotation around the vertical axis.

### Roll, pitch, yaw
The three Euler angles in 3D. Roll (around X, lateral tilt), pitch (around Y, nose up/down), yaw (around Z, heading).

### Euler angles
Parameterization of 3D rotations by three successive angles. Intuitive but suffers from **gimbal lock** (loss of one degree of freedom when two axes align).

### Quaternion
Parameterization of 3D rotations by four numbers `(w, x, y, z)` with `w² + x² + y² + z² = 1`. No gimbal lock, fast composition, clean interpolation (slerp). Used internally by `Pose3D`.

### Rotation matrix
Orthogonal 2×2 in 2D, 3×3 in 3D. Most direct representation, but redundant (9 numbers for 3 DOF in 3D).

---

## Frame / reference concepts

### Parent frame
The frame in which a pose is **expressed**. The table is typically the parent of the robot.

### Local (child) frame
The frame defined by the pose itself. The robot frame, in which positions are expressed **relative to the robot**.

### Local coordinates
Coordinates of a point expressed in a local frame (e.g. in the lidar frame).

### Global coordinates
Coordinates in a root frame (e.g. on the table).

### Change of frame
Converting a point from local to global coordinates (or the reverse). Exactly `pose.transform(point)` and `pose.inverse().transform(point)`.

---

## Usual robotics concepts

### Odometry
Pose estimation by integrating measured displacements (wheel encoders). Accumulates in `SE(2)` step by step. Drifts over time.

### SLAM
Simultaneous Localization And Mapping. Builds a map **and** localizes in it at the same time. Heavy user of `SE(2)` / `SE(3)` poses.

### Kinematics
Study of motion without regard to forces. `SE(n)` transformations are the base tool.

### Forward kinematics
Given arm joint angles, where is the gripper? `SE(3)` composition along each segment.

### Inverse kinematics
Given a desired gripper pose, what joint angles? Reverse problem, usually iterative.

### Rigid body
A body that does not deform. Its position and orientation are fully described by an element of `SE(n)`.

---

## This library's notation

| Symbol | Meaning |
|--------|---------|
| `Pose2D(x, y, theta)` | Element of SE(2). Position in mm, orientation in radians. |
| `Pose3D(x, y, z, roll, pitch, yaw)` | Element of SE(3). Position in mm, orientation stored as quaternion internally. |
| `Vect2D(x, y)`, `Vect3D(x, y, z)` | Vectors / points in `ℝ²` and `ℝ³`. Addable, scalable, normable. |
| `transform(point)` | Action of a pose on a point: local → parent coordinates. |
| `compose(other)` | Multiplication in `SE(n)`: chain two transformations or frames. |
| `inverse()` | Inverse in `SE(n)`: child frame → parent frame. |
| `RigidTransform2D` | Same object as `Pose2D`, but with a mutable API (`apply_to_point` modifies in place). Useful for chaining without allocating. |
| `AffineTransform2D` | `RigidTransform2D` + scaling. **Leaves** SE(2), goes into the bigger affine group. Does not preserve distances. |
| `MirrorTransform2D` | Axial symmetry. **Also leaves** SE(2) (determinant = -1, lands in E(2)). Useful for mirroring strategies across the table side. |

---

## Takeaway: four words to remember

1. **Point** (location) ≠ **vector** (displacement) ≠ **pose** (frame).
2. You **compose** two poses, and you **transform** a point with a pose. Never the other way around.
3. Angles live on a **circle**: never add or average them like plain reals without `normalize_angle` afterward.
4. **SE(n)** = "position + orientation with group structure". It is **not** a vector space.

Everything else (Lie theory, quaternion math, manifolds) only matters for advanced topics (Kalman filtering, graph SLAM, optimal control).
